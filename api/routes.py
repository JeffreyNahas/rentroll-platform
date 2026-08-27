"""Typed GET endpoints. One SQL string per path; the model never invents it.

Three routers so `/docs` still groups portfolio / properties / metrics.
Prefixes are applied in `api/app.py`.
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from psycopg import Connection

from api.db import readonly_conn, settings
from api.envelope import ApiWarning, build_sources, envelope, mask_display_name

portfolio = APIRouter()
properties = APIRouter()
metrics = APIRouter()

PROPERTY_TYPES = ("residential", "affordable", "commercial", "land", "other")
LTL_TYPES_IN_SCOPE = frozenset({"residential", "affordable"})
LEASE_SECTIONS = ("current", "future")


def _fmt_money(x: Decimal | float | None) -> str:
    if x is None:
        return "n/a"
    return f"${float(x):,.2f}"


def _note_for(check_name: str, code: str, subject: str,
              expected, actual, delta) -> str:
    """Human-readable one-liner so a reviewer doesn't have to decode the
    (expected, actual, delta) tuple. See design rule #6: surface data
    problems, don't hide them."""
    if check_name == "charge_code":
        return (
            f"File-level charge summary on {code} reports "
            f"{_fmt_money(expected)} for {subject}, but individual charges "
            f"sum to {_fmt_money(actual)} "
            f"(delta {_fmt_money(delta)}). Trust the per-lease sum; the "
            "file's summary block is internally inconsistent."
        )
    if check_name == "lease_v_units":
        return (
            f"Cross-report disagreement on {code}: rent roll contains "
            f"{int(actual)} current-section lease(s), availability report "
            f"shows total_units = {int(expected)}. Occupancy for {code} "
            "uses rent_roll_derived as the authoritative source."
        )
    if check_name == "unclassified_units":
        return (
            f"Availability report for {code} counts {int(actual)} unit(s) "
            "that are not classified into any Occupied/Vacant/Notice state. "
            "Commercial residential-vocabulary gap; states_reconcile=false. "
            "Never redistributed across the states, never hidden."
        )
    return ""


def _filter_clause(
    conn: Connection,
    *,
    property_type: str | None,
    property_code: str | None,
) -> tuple[str, list[Any], list[str]]:
    """Build `WHERE …` and the property_code list the sources block should
    cite. Returns (sql_where, params, cited_property_codes | None-if-all).
    """
    where: list[str] = []
    params: list[Any] = []
    cited_codes: list[str] | None = None

    if property_type:
        if property_type not in PROPERTY_TYPES:
            raise HTTPException(400, f"unknown property_type {property_type!r}")
        where.append("property_type = %s")
        params.append(property_type)

    if property_code:
        exists = conn.execute(
            "SELECT 1 FROM property WHERE property_code = %s", (property_code,)
        ).fetchone()
        if not exists:
            raise HTTPException(404, f"unknown property_code {property_code!r}")
        where.append("property_code = %s")
        params.append(property_code)
        cited_codes = [property_code]

    if property_type and not property_code:
        rows = conn.execute(
            "SELECT property_code FROM property WHERE property_type = %s",
            (property_type,),
        ).fetchall()
        cited_codes = [r["property_code"] for r in rows]

    sql_where = ("WHERE " + " AND ".join(where)) if where else ""
    return sql_where, params, cited_codes


# ── portfolio ─────────────────────────────────────────────────────────────
@portfolio.get("/summary", summary="Portfolio KPIs segmented by property_type")
def portfolio_summary() -> dict:
    """One row per property_type. Ratios weighted within type; never blended
    across types (design rule #4)."""
    started = time.perf_counter()
    with readonly_conn() as conn:
        rows = conn.execute("""
            SELECT property_type, n_properties, total_units, non_revenue_units,
                   unclassified_units, total_rentable_units,
                   total_occupied_units, total_notice_units, total_vacant_units,
                   n_leases_current, n_leases_notice, n_leases_vacant,
                   total_market_rent, total_base_rent, pct_occupied
            FROM v_portfolio_summary_by_type
            ORDER BY property_type
        """).fetchall()
        sources = build_sources(conn)
    return envelope(rows, sources, started)


@portfolio.get("/data-quality", summary="Long-form data-quality metrics")
def data_quality() -> dict:
    """Backs the dashboard's data-quality *summary* tile. Counts only. For
    the specific failures behind the counts, call
    `/portfolio/data-quality/failures`."""
    started = time.perf_counter()
    with readonly_conn() as conn:
        rows = conn.execute("""
            SELECT metric_name, value FROM v_data_quality_summary
        """).fetchall()
        sources = build_sources(conn)
    return envelope(rows, sources, started)


@portfolio.get(
    "/data-quality/failures",
    summary="One row per data-quality problem, with a human-readable note",
)
def data_quality_failures() -> dict:
    """The details behind `/portfolio/data-quality`. Reviewer opens this
    and sees exactly what is wrong with which property -- no psql required.

    Row shape is uniform across kinds:
        check_name        one of: charge_code, lease_total, lease_v_units,
                          unclassified_units
        property_code     which property
        subject           the specific thing (charge code / property_code / …)
        expected / actual / delta   as recorded in ingest_audit
        note              one-sentence English explanation
    """
    started = time.perf_counter()
    with readonly_conn() as conn:
        audit_rows = conn.execute("""
            SELECT a.check_name, p.property_code, p.property_name,
                   p.property_type, a.subject,
                   a.expected, a.actual, a.delta
            FROM ingest_audit a
            JOIN report_snapshot rs ON rs.snapshot_id = a.snapshot_id
            JOIN property p         ON p.property_id  = rs.property_id
            WHERE NOT a.passed
            ORDER BY p.property_code, a.check_name, a.subject
        """).fetchall()

        unclassified_rows = conn.execute("""
            SELECT p.property_code, p.property_name, p.property_type,
                   pa.unclassified_units
            FROM property_availability pa
            JOIN v_latest_snapshot ls
                 ON  ls.snapshot_id = pa.snapshot_id
                 AND ls.report_type = 'unit_availability'
            JOIN property p ON p.property_id = pa.property_id
            WHERE pa.unclassified_units > 0
            ORDER BY p.property_code
        """).fetchall()

        rows: list[dict] = []
        for r in audit_rows:
            rows.append({
                **r,
                "note": _note_for(
                    r["check_name"], r["property_code"], r["subject"],
                    r["expected"], r["actual"], r["delta"],
                ),
            })
        for r in unclassified_rows:
            rows.append({
                "check_name":    "unclassified_units",
                "property_code": r["property_code"],
                "property_name": r["property_name"],
                "property_type": r["property_type"],
                "subject":       r["property_code"],
                "expected":      0,
                "actual":        r["unclassified_units"],
                "delta":         r["unclassified_units"],
                "note": _note_for(
                    "unclassified_units", r["property_code"],
                    r["property_code"], 0,
                    r["unclassified_units"], r["unclassified_units"],
                ),
            })

        cited_codes = sorted({r["property_code"] for r in rows})
        sources = build_sources(conn, property_codes=cited_codes)

    return envelope(rows, sources, started)


# ── properties ────────────────────────────────────────────────────────────
@properties.get("", summary="All properties (no snapshot data)")
def list_properties(
    property_type: str | None = Query(None),
) -> dict:
    """Dimension read. Doesn't touch snapshots, but cites all snapshots for
    consistency with the rest of the API."""
    started = time.perf_counter()
    with readonly_conn() as conn:
        if property_type:
            rows = conn.execute("""
                SELECT property_id, property_code, property_name, property_type
                FROM property WHERE property_type = %s ORDER BY property_code
            """, (property_type,)).fetchall()
            cited = [r["property_code"] for r in rows]
        else:
            rows = conn.execute("""
                SELECT property_id, property_code, property_name, property_type
                FROM property ORDER BY property_code
            """).fetchall()
            cited = None
        sources = build_sources(conn, property_codes=cited)
    return envelope(rows, sources, started)


@properties.get("/{code}", summary="One property: occupancy + charge mix")
def property_detail(code: str) -> dict:
    """Fat detail response: everything the dashboard needs on a property
    drill-in without a second round trip."""
    started = time.perf_counter()
    with readonly_conn() as conn:
        occ = conn.execute("""
            SELECT * FROM v_occupancy_by_property WHERE property_code = %s
        """, (code,)).fetchone()
        if occ is None:
            raise HTTPException(404, f"unknown property_code {code!r}")

        charges = conn.execute("""
            SELECT category, sum_amount, n_charges, pct_of_property_gross
            FROM v_charge_mix_by_property
            WHERE property_code = %s ORDER BY category
        """, (code,)).fetchall()

        delinq = conn.execute("""
            SELECT n_active_leases, n_delinquent_leases, total_balance_owed,
                   pct_leases_delinquent, avg_delinquent_balance
            FROM v_delinquency_by_property
            WHERE property_code = %s
        """, (code,)).fetchone()

        ltl = conn.execute("""
            SELECT units_in_scope, market_rent_total, effective_rent_total,
                   loss_to_lease, pct_loss_to_lease
            FROM v_loss_to_lease
            WHERE property_code = %s
        """, (code,)).fetchone()

        sources = build_sources(conn, property_codes=[code])

    data = [{
        "occupancy": occ,
        "charge_mix": charges,
        "delinquency": delinq,
        "loss_to_lease": ltl,
    }]
    return envelope(data, sources, started)


@properties.get("/{code}/leases", summary="Lease detail for a property")
def property_leases(
    code: str,
    section: str = Query(
        "current",
        description=(
            "'current' = the Current/Notice/Vacant section (default). "
            "'future' = signed-but-not-moved-in applicants; these are "
            "excluded from occupancy on purpose."
        ),
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    """Row-level leases. Paginated (default 100). Respects `MASK_PII`.

    `?section=future` returns the 93 portfolio-wide applicants — signed
    but not moved in — that would inflate occupancy if counted. Kept as
    a filter (not a separate endpoint) so the same row schema serves both.
    """
    if section not in LEASE_SECTIONS:
        raise HTTPException(
            400, f"unknown section {section!r}; must be one of {list(LEASE_SECTIONS)}"
        )

    started = time.perf_counter()
    with readonly_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM property WHERE property_code = %s", (code,)
        ).fetchone()
        if not exists:
            raise HTTPException(404, f"unknown property_code {code!r}")

        rows = conn.execute("""
            SELECT lease_id, snapshot_id, source_row, as_of_date,
                   property_code, property_type, unit_id, unit_number,
                   square_feet, unit_type_code,
                   resident_id, resident_code, display_name,
                   section, lease_status, is_vacant,
                   market_rent, resident_deposit, other_deposit, balance,
                   move_in_date, lease_expiration, move_out_date,
                   reported_total, base_rent_actual
            FROM v_lease_detail
            WHERE property_code = %s AND section = %s
            ORDER BY unit_number
            LIMIT %s OFFSET %s
        """, (code, section, limit, offset)).fetchall()

        for row in rows:
            mask_display_name(row, mask=settings.mask_pii)

        total = conn.execute(
            "SELECT count(*) AS c FROM v_lease_detail "
            "WHERE property_code = %s AND section = %s",
            (code, section),
        ).fetchone()["c"]

        sources = build_sources(conn, property_codes=[code],
                                report_types=["rent_roll"])

    warnings: list[ApiWarning] = []
    if section == "future":
        warnings.append(ApiWarning(
            code="future_applicants",
            message=(
                "These are signed leases with no move-in yet. They are "
                "excluded from occupancy, loss-to-lease, delinquency, and "
                "the expiration schedule by design; counting them would "
                "inflate occupancy by 93 units portfolio-wide."
            ),
        ))

    env = envelope(rows, sources, started, warnings)
    env["pagination"] = {"limit": limit, "offset": offset, "total": total,
                         "section": section}
    return env


# ── metrics ───────────────────────────────────────────────────────────────
@metrics.get("/occupancy", summary="Occupancy per property, with occupancy_source")
def occupancy(
    property_type: str | None = Query(None, description="Filter by property_type"),
    property_code: str | None = Query(None, description="Filter by property_code"),
) -> dict:
    started = time.perf_counter()
    with readonly_conn() as conn:
        where, params, cited = _filter_clause(
            conn, property_type=property_type, property_code=property_code
        )
        rows = conn.execute(f"""
            SELECT property_id, property_code, property_name, property_type,
                   as_of_date, occupancy_source,
                   total_units, non_revenue_units, unclassified_units,
                   rentable_units, occupied_units, notice_units, vacant_units,
                   pct_occupied, pct_occupied_with_notice
            FROM v_occupancy_by_property
            {where}
            ORDER BY property_code
        """, params).fetchall()
        sources = build_sources(conn, property_codes=cited)

    warnings: list[ApiWarning] = []
    fallbacks = [
        r["property_code"] for r in rows
        if r["occupancy_source"] == "rent_roll_derived"
    ]
    if fallbacks:
        warnings.append(ApiWarning(
            code="occupancy_source_fallback",
            message=(
                f"Occupancy for {len(fallbacks)} propert"
                f"{'y' if len(fallbacks) == 1 else 'ies'} "
                f"({', '.join(fallbacks)}) is derived from the rent roll "
                "because the availability report's states don't reconcile. "
                "Numerator and denominator both come from the rent roll "
                "in these cases; see docs/data_quality.md."
            ),
        ))
    return envelope(rows, sources, started, warnings)


@metrics.get("/loss-to-lease", summary="Market vs effective base rent")
def loss_to_lease(
    property_type: str | None = Query(None),
    property_code: str | None = Query(None),
) -> dict:
    started = time.perf_counter()
    with readonly_conn() as conn:
        where, params, cited = _filter_clause(
            conn, property_type=property_type, property_code=property_code
        )
        rows = conn.execute(f"""
            SELECT property_id, property_code, property_name, property_type,
                   as_of_date, units_in_scope, market_rent_total,
                   effective_rent_total, loss_to_lease, pct_loss_to_lease
            FROM v_loss_to_lease
            {where}
            ORDER BY property_code
        """, params).fetchall()
        sources = build_sources(conn, property_codes=cited)

    warnings: list[ApiWarning] = []
    if property_type and property_type not in LTL_TYPES_IN_SCOPE:
        warnings.append(ApiWarning(
            code="loss_to_lease_out_of_scope",
            message=(
                f"Loss-to-lease is only defined for residential and "
                f"affordable properties. {property_type} was requested; "
                "commercial market_rent is 0 in the source, land and "
                "management entities have no leases. Empty result is by "
                "design, not by data loss."
            ),
        ))
    return envelope(rows, sources, started, warnings)


@metrics.get("/delinquency", summary="Balances owed per property")
def delinquency(
    property_type: str | None = Query(None),
    property_code: str | None = Query(None),
) -> dict:
    started = time.perf_counter()
    with readonly_conn() as conn:
        where, params, cited = _filter_clause(
            conn, property_type=property_type, property_code=property_code
        )
        rows = conn.execute(f"""
            SELECT property_id, property_code, property_name, property_type,
                   as_of_date, n_active_leases, n_delinquent_leases,
                   total_balance_owed, pct_leases_delinquent,
                   max_balance, avg_delinquent_balance
            FROM v_delinquency_by_property
            {where}
            ORDER BY property_code
        """, params).fetchall()
        sources = build_sources(conn, property_codes=cited)
    return envelope(rows, sources, started)


@metrics.get("/charge-mix", summary="Revenue mix by charge category")
def charge_mix(
    property_type: str | None = Query(None),
    property_code: str | None = Query(None),
) -> dict:
    started = time.perf_counter()
    with readonly_conn() as conn:
        where, params, cited = _filter_clause(
            conn, property_type=property_type, property_code=property_code
        )
        rows = conn.execute(f"""
            SELECT property_id, property_code, property_name, property_type,
                   as_of_date, category, sum_amount, n_charges,
                   pct_of_property_gross
            FROM v_charge_mix_by_property
            {where}
            ORDER BY property_code, category
        """, params).fetchall()
        sources = build_sources(conn, property_codes=cited,
                                report_types=["rent_roll"])
    return envelope(rows, sources, started)


@metrics.get("/expirations", summary="Lease expiration schedule by month")
def expirations(
    property_type: str | None = Query(None),
    property_code: str | None = Query(None),
    date_from: str | None = Query(None, alias="from",
                                  description="ISO date, inclusive"),
    date_to: str | None = Query(None, alias="to",
                                description="ISO date, inclusive"),
) -> dict:
    started = time.perf_counter()
    with readonly_conn() as conn:
        where, params, cited = _filter_clause(
            conn, property_type=property_type, property_code=property_code
        )
        clauses = [where[6:]] if where else []       # strip leading 'WHERE '
        if date_from:
            clauses.append("expiration_month >= %s")
            params.append(date_from)
        if date_to:
            clauses.append("expiration_month <= %s")
            params.append(date_to)
        final_where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        rows = conn.execute(f"""
            SELECT property_id, property_code, property_name, property_type,
                   as_of_date, expiration_month, n_leases_expiring,
                   market_rent_expiring, base_rent_expiring
            FROM v_expirations_by_month
            {final_where}
            ORDER BY property_code, expiration_month
        """, params).fetchall()
        sources = build_sources(conn, property_codes=cited,
                                report_types=["rent_roll"])
    return envelope(rows, sources, started)
