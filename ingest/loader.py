"""Parse Excel files and load them into the database.

Design choices worth calling out:

* **One transaction per file.** A bad row in 462a doesn't roll back the 108
  files loaded before it. But within a file, either everything commits or
  nothing does -- no half-loaded snapshots.

* **SHA-256 file hash for idempotency.** `make load` can be re-run at will;
  files already present in `source_file` are skipped without reparsing. This
  is why re-running is a no-op rather than a duplicate-key crash.

* **Charge codes are pre-validated.** Any charge code not present in the
  `charge_code` dim table causes the file to fail with a load-time error
  rather than a silent FK violation halfway through insertion. Per the
  design rules an unmapped code is never allowed to become a silent `other`.

* **Bronze layer.** Every source row is written to `raw_row` as JSONB so a
  future parser change can be replayed without re-reading the spreadsheets.

* **Reconciliation lives in the database.** Every per-lease `Total`, every
  file-level charge-code summary line, and every per-property
  `current-section leases == total_units` check writes a row to
  `ingest_audit`. That table is the source of truth for a data-quality
  panel later, not a script-time print.
"""

from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from ingest.models import FileHeader
from ingest.normalize import property_type
from ingest.parsers import (
    parse_availability,
    parse_charge_summary,
    parse_rent_roll,
)

PARSER_VERSION = "0.1.0"
CENT = Decimal("0.01")

RENT_ROLL_DIR = "Rent_Roll_with_Lease_Charges"
AVAILABILITY_DIR = "Unit_Availability"


# ────────────────────────────────────────────────────────────────────────────
# Result plumbing
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class LoadResult:
    path: Path
    status: str                       # 'loaded' | 'skipped' | 'error'
    report_type: str
    property_code: str | None = None
    n_rows: int = 0
    n_leases: int = 0
    n_charges: int = 0
    n_warnings: int = 0
    audits_pass: int = 0
    audits_fail: int = 0
    error: str | None = None


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _dsn() -> str:
    """SQLAlchemy-style DSNs from .env aren't psycopg-native. Strip the driver."""
    return os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_safe(value):
    """Coerce spreadsheet cell values into JSON-serialisable form for raw_row."""
    if value is None:
        return None
    if isinstance(value, float):
        return None if math.isnan(value) else value
    if isinstance(value, (int, str, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _is_source_file(path: Path) -> bool:
    return path.is_file() and not path.name.startswith("~$")


# ────────────────────────────────────────────────────────────────────────────
# Upserts on dimensions
# ────────────────────────────────────────────────────────────────────────────


def upsert_property(conn: psycopg.Connection, header: FileHeader) -> int:
    row = conn.execute(
        """
        INSERT INTO property (property_code, property_name, property_type)
        VALUES (%s, %s, %s)
        ON CONFLICT (property_code) DO UPDATE
          SET property_name = EXCLUDED.property_name
        RETURNING property_id
        """,
        (header.property_code, header.property_name,
         property_type(header.property_code)),
    ).fetchone()
    return row[0]


def upsert_unit_type(conn: psycopg.Connection, property_id: int, code: str) -> int:
    # DO NOTHING would skip the RETURNING, so touch the row on conflict.
    row = conn.execute(
        """
        INSERT INTO unit_type (property_id, code)
        VALUES (%s, %s)
        ON CONFLICT (property_id, code) DO UPDATE SET code = EXCLUDED.code
        RETURNING unit_type_id
        """,
        (property_id, code),
    ).fetchone()
    return row[0]


def upsert_unit(conn: psycopg.Connection, property_id: int, unit_number: str,
                unit_type_id: int | None, square_feet: int | None) -> int:
    row = conn.execute(
        """
        INSERT INTO unit (property_id, unit_number, unit_type_id, square_feet)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (property_id, unit_number) DO UPDATE
          SET unit_type_id = COALESCE(EXCLUDED.unit_type_id, unit.unit_type_id),
              square_feet  = COALESCE(EXCLUDED.square_feet,  unit.square_feet)
        RETURNING unit_id
        """,
        (property_id, unit_number, unit_type_id, square_feet),
    ).fetchone()
    return row[0]


def upsert_resident(conn: psycopg.Connection, property_id: int,
                    resident_code: str, display_name: str | None) -> int:
    row = conn.execute(
        """
        INSERT INTO resident (property_id, resident_code, display_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (property_id, resident_code) DO UPDATE
          SET display_name = COALESCE(EXCLUDED.display_name, resident.display_name)
        RETURNING resident_id
        """,
        (property_id, resident_code, display_name),
    ).fetchone()
    return row[0]


# ────────────────────────────────────────────────────────────────────────────
# Provenance rows
# ────────────────────────────────────────────────────────────────────────────


def insert_source_file(conn: psycopg.Connection, path: Path, file_hash: str,
                       report_type: str, n_rows: int) -> int:
    row = conn.execute(
        """
        INSERT INTO source_file (filename, file_hash, report_type, n_rows, parser_version)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING source_file_id
        """,
        (path.name, file_hash, report_type, n_rows, PARSER_VERSION),
    ).fetchone()
    return row[0]


def insert_snapshot(conn: psycopg.Connection, source_file_id: int, property_id: int,
                    report_type: str, as_of: date) -> int:
    row = conn.execute(
        """
        INSERT INTO report_snapshot (source_file_id, property_id, report_type, as_of_date)
        VALUES (%s, %s, %s, %s)
        RETURNING snapshot_id
        """,
        (source_file_id, property_id, report_type, as_of),
    ).fetchone()
    return row[0]


def insert_raw_rows(conn: psycopg.Connection, source_file_id: int,
                    df: pd.DataFrame) -> None:
    """Bronze: keep every source row verbatim as JSONB, indexed by row number."""
    payloads = [
        (source_file_id, i, Jsonb([_json_safe(v) for v in row]))
        for i, row in enumerate(df.itertuples(index=False, name=None))
    ]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO raw_row (source_file_id, source_row, payload) "
            "VALUES (%s, %s, %s)",
            payloads,
        )


def load_charge_codes(conn: psycopg.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT charge_code FROM charge_code")}


# ────────────────────────────────────────────────────────────────────────────
# Rent roll load
# ────────────────────────────────────────────────────────────────────────────


def _lease_totals_audit(conn, snapshot_id, leases) -> tuple[int, int]:
    """Insert one audit row per lease whose block carries a Total. Returns
    (pass_count, fail_count)."""
    rows = []
    passed = failed = 0
    for lease in leases:
        if lease.reported_total is None:
            continue
        computed = lease.charge_total()
        delta = computed - lease.reported_total
        ok = abs(delta) <= CENT
        rows.append((snapshot_id, "lease_total", lease.unit_number,
                     lease.reported_total, computed, delta, ok))
        if ok:
            passed += 1
        else:
            failed += 1
    if rows:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO ingest_audit (snapshot_id, check_name, subject,
                                          expected, actual, delta, passed)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
    return passed, failed


def _charge_summary_audit(conn, snapshot_id, leases, summary) -> tuple[int, int]:
    """Insert one audit row per charge code in the file-level summary, plus
    one for the grand total. Also flag codes present in leases but absent
    from the summary."""
    computed_by_code: dict[str, Decimal] = {}
    for lease in leases:
        for ch in lease.charges:
            computed_by_code[ch.charge_code] = (
                computed_by_code.get(ch.charge_code, Decimal(0)) + ch.amount
            )

    rows = []
    passed = failed = 0

    for code, reported in summary.items():
        if code == "__TOTAL__":
            continue
        computed = computed_by_code.get(code, Decimal(0))
        delta = computed - (reported if reported is not None else Decimal(0))
        ok = reported is not None and abs(delta) <= CENT
        rows.append((snapshot_id, "charge_code", code,
                     reported, computed, delta, ok))
        if ok:
            passed += 1
        else:
            failed += 1

    # Codes present in the leases but missing from the summary block.
    for code, computed in computed_by_code.items():
        if code not in summary and computed != 0:
            rows.append((snapshot_id, "charge_code", code,
                         None, computed, computed, False))
            failed += 1

    total_reported = summary.get("__TOTAL__")
    total_computed = sum(computed_by_code.values(), Decimal(0))
    if total_reported is not None:
        delta = total_computed - total_reported
        ok = abs(delta) <= CENT
        rows.append((snapshot_id, "charge_code", "__TOTAL__",
                     total_reported, total_computed, delta, ok))
        if ok:
            passed += 1
        else:
            failed += 1

    if rows:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO ingest_audit (snapshot_id, check_name, subject,
                                          expected, actual, delta, passed)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
    return passed, failed


def _write_warnings(conn, source_file_id, warnings) -> None:
    if not warnings:
        return
    rows = [(source_file_id, "warn", "parse", w) for w in warnings]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO ingest_error (source_file_id, severity, stage, message)
            VALUES (%s, %s, %s, %s)
            """,
            rows,
        )


def load_rent_roll(conn: psycopg.Connection, path: Path,
                   known_codes: set[str]) -> LoadResult:
    result = LoadResult(path=path, status="error", report_type="rent_roll")

    file_hash = sha256_file(path)
    if conn.execute(
        "SELECT 1 FROM source_file WHERE file_hash = %s", (file_hash,)
    ).fetchone():
        result.status = "skipped"
        return result

    header, leases, warnings = parse_rent_roll(path)
    summary = parse_charge_summary(path)
    df = pd.read_excel(path, header=None)

    # Fail-fast on unmapped charge codes before we start writing anything.
    seen = {ch.charge_code for l in leases for ch in l.charges}
    unknown = seen - known_codes
    if unknown:
        result.error = f"unknown charge codes: {sorted(unknown)}"
        return result

    with conn.transaction():
        property_id = upsert_property(conn, header)
        source_file_id = insert_source_file(
            conn, path, file_hash, "rent_roll", len(df)
        )
        snapshot_id = insert_snapshot(
            conn, source_file_id, property_id, "rent_roll", header.as_of_date
        )
        insert_raw_rows(conn, source_file_id, df)

        n_charges = 0
        for lease in leases:
            unit_type_id = (
                upsert_unit_type(conn, property_id, lease.unit_type)
                if lease.unit_type else None
            )
            unit_id = upsert_unit(
                conn, property_id, lease.unit_number,
                unit_type_id, lease.square_feet,
            )
            resident_id = None
            if not lease.is_vacant and lease.resident_code:
                resident_id = upsert_resident(
                    conn, property_id,
                    lease.resident_code, lease.resident_name,
                )

            lease_id = conn.execute(
                """
                INSERT INTO lease (
                    snapshot_id, unit_id, resident_id, section, lease_status,
                    is_vacant, market_rent, resident_deposit, other_deposit,
                    balance, move_in_date, lease_expiration, move_out_date,
                    reported_total, source_row
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                          %s, %s, %s, %s, %s)
                RETURNING lease_id
                """,
                (snapshot_id, unit_id, resident_id, lease.section,
                 lease.lease_status, lease.is_vacant, lease.market_rent,
                 lease.resident_deposit, lease.other_deposit, lease.balance,
                 lease.move_in_date, lease.lease_expiration,
                 lease.move_out_date, lease.reported_total, lease.source_row),
            ).fetchone()[0]

            if lease.charges:
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO lease_charge
                          (lease_id, charge_code, amount, source_row)
                        VALUES (%s, %s, %s, %s)
                        """,
                        [(lease_id, c.charge_code, c.amount, c.source_row)
                         for c in lease.charges],
                    )
                n_charges += len(lease.charges)

        p1, f1 = _lease_totals_audit(conn, snapshot_id, leases)
        p2, f2 = (0, 0)
        if summary:
            p2, f2 = _charge_summary_audit(conn, snapshot_id, leases, summary)

        _write_warnings(conn, source_file_id, warnings)

    result.status = "loaded"
    result.property_code = header.property_code
    result.n_rows = len(df)
    result.n_leases = len(leases)
    result.n_charges = n_charges
    result.n_warnings = len(warnings)
    result.audits_pass = p1 + p2
    result.audits_fail = f1 + f2
    return result


# ────────────────────────────────────────────────────────────────────────────
# Availability load
# ────────────────────────────────────────────────────────────────────────────


def load_availability(conn: psycopg.Connection, path: Path) -> LoadResult:
    result = LoadResult(path=path, status="error", report_type="unit_availability")

    file_hash = sha256_file(path)
    if conn.execute(
        "SELECT 1 FROM source_file WHERE file_hash = %s", (file_hash,)
    ).fetchone():
        result.status = "skipped"
        return result

    header, record = parse_availability(path)
    df = pd.read_excel(path, header=None)

    with conn.transaction():
        property_id = upsert_property(conn, header)
        source_file_id = insert_source_file(
            conn, path, file_hash, "unit_availability", len(df)
        )
        snapshot_id = insert_snapshot(
            conn, source_file_id, property_id,
            "unit_availability", header.as_of_date,
        )
        insert_raw_rows(conn, source_file_id, df)

        conn.execute(
            """
            INSERT INTO property_availability (
                snapshot_id, property_id, avg_square_feet, avg_rent, total_units,
                occupied_no_notice, vacant_rented, vacant_unrented,
                notice_rented, notice_unrented, available,
                model_units, down_units, admin_units,
                pct_occupied, pct_occupied_nonrev, pct_leased, pct_trend,
                unclassified_units, states_reconcile, source_row
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s, %s, %s)
            """,
            (snapshot_id, property_id, record.avg_square_feet, record.avg_rent,
             record.total_units, record.occupied_no_notice, record.vacant_rented,
             record.vacant_unrented, record.notice_rented, record.notice_unrented,
             record.available, record.model_units, record.down_units,
             record.admin_units, record.pct_occupied, record.pct_occupied_nonrev,
             record.pct_leased, record.pct_trend, record.unclassified_units,
             record.states_reconcile, record.source_row),
        )

    result.status = "loaded"
    result.property_code = header.property_code
    result.n_rows = len(df)
    return result


# ────────────────────────────────────────────────────────────────────────────
# Cross-report audit
# ────────────────────────────────────────────────────────────────────────────


def write_lease_vs_units_audits(conn: psycopg.Connection) -> int:
    """For each property with both reports at the latest as_of_date, insert
    one audit row comparing `count(current-section leases)` against
    `property_availability.total_units`.

    Attached to the rent-roll snapshot -- that's the side whose parser this
    check exercises.
    """
    rows = conn.execute("""
        WITH rr_latest AS (
            SELECT DISTINCT ON (property_id) snapshot_id, property_id, as_of_date
            FROM report_snapshot
            WHERE report_type = 'rent_roll'
            ORDER BY property_id, as_of_date DESC
        ),
        av_latest AS (
            SELECT DISTINCT ON (property_id) snapshot_id, property_id
            FROM report_snapshot
            WHERE report_type = 'unit_availability'
            ORDER BY property_id, as_of_date DESC
        ),
        counts AS (
            SELECT rr.snapshot_id  AS rr_snap,
                   p.property_code,
                   pa.total_units,
                   (SELECT count(*) FROM lease
                    WHERE snapshot_id = rr.snapshot_id AND section = 'current')
                     AS current_leases
            FROM rr_latest rr
            JOIN av_latest av USING (property_id)
            JOIN property p ON p.property_id = rr.property_id
            JOIN property_availability pa ON pa.snapshot_id = av.snapshot_id
        )
        INSERT INTO ingest_audit (snapshot_id, check_name, subject,
                                  expected, actual, delta, passed)
        SELECT rr_snap, 'lease_v_units', property_code,
               total_units, current_leases,
               current_leases - total_units,
               current_leases = total_units
        FROM counts
        RETURNING 1
    """).fetchall()
    return len(rows)


# ────────────────────────────────────────────────────────────────────────────
# Directory-level orchestrator
# ────────────────────────────────────────────────────────────────────────────


def _record_error(dsn: str, path: Path, message: str) -> None:
    """Errors are written in a fresh connection so a rolled-back file
    transaction doesn't take the error record down with it."""
    with psycopg.connect(dsn, autocommit=True) as err_conn:
        err_conn.execute(
            """
            INSERT INTO ingest_error (source_file_id, severity, stage, message)
            VALUES (NULL, 'error', 'load', %s)
            """,
            (f"{path.name}: {message}",),
        )


def load_directory(dsn: str, root: Path, *, verbose: bool = True) -> list[LoadResult]:
    results: list[LoadResult] = []
    with psycopg.connect(dsn) as conn:
        known_codes = load_charge_codes(conn)

        rent_rolls = sorted(p for p in (root / RENT_ROLL_DIR).glob("*.xls*")
                            if _is_source_file(p))
        availability = sorted(p for p in (root / AVAILABILITY_DIR).glob("*.xls*")
                              if _is_source_file(p))

        for path in rent_rolls:
            try:
                result = load_rent_roll(conn, path, known_codes)
                conn.commit()
            except Exception as exc:                      # noqa: BLE001
                conn.rollback()
                result = LoadResult(path=path, status="error",
                                    report_type="rent_roll", error=str(exc))
                _record_error(dsn, path, str(exc))
            results.append(result)
            if verbose:
                print(_format(result))

        for path in availability:
            try:
                result = load_availability(conn, path)
                conn.commit()
            except Exception as exc:                      # noqa: BLE001
                conn.rollback()
                result = LoadResult(path=path, status="error",
                                    report_type="unit_availability", error=str(exc))
                _record_error(dsn, path, str(exc))
            results.append(result)
            if verbose:
                print(_format(result))

        # Only re-run cross-report audits if we actually loaded something.
        # Re-running on an all-skipped invocation would double the rows.
        if any(r.status == "loaded" for r in results):
            n_cross = write_lease_vs_units_audits(conn)
            conn.commit()
            if verbose:
                print(f"\ncross-report audits written: {n_cross}")
        elif verbose:
            print("\ncross-report audits: skipped (no new files loaded)")

    return results


def _format(r: LoadResult) -> str:
    tag = {"loaded": "OK", "skipped": "skip", "error": "ERROR"}[r.status]
    prefix = f"  [{tag:>6}] {(r.property_code or '?'):<8} {r.report_type:<18}"
    if r.status == "loaded" and r.report_type == "rent_roll":
        return (f"{prefix} leases={r.n_leases:<4} charges={r.n_charges:<5} "
                f"audits {r.audits_pass}/{r.audits_pass + r.audits_fail} "
                f"warn={r.n_warnings}  {r.path.name}")
    if r.status == "loaded":
        return f"{prefix} {r.path.name}"
    if r.status == "skipped":
        return f"{prefix} {r.path.name}  (hash already loaded)"
    return f"{prefix} {r.path.name}  -- {r.error}"


def main() -> int:
    load_dotenv()
    root = Path(os.environ.get("INGEST_DIR", "data/raw"))
    results = load_directory(_dsn(), root)

    loaded = sum(1 for r in results if r.status == "loaded")
    skipped = sum(1 for r in results if r.status == "skipped")
    errored = sum(1 for r in results if r.status == "error")
    audits_pass = sum(r.audits_pass for r in results)
    audits_fail = sum(r.audits_fail for r in results)

    print("\n" + "=" * 60)
    print(f"loaded={loaded}  skipped={skipped}  errored={errored}")
    print(f"audits: {audits_pass} pass, {audits_fail} fail")
    return 0 if errored == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
