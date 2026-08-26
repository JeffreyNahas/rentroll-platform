"""Portfolio-wide rollups. No filters -- these views are the top of the
dashboard and always show the whole book."""

from __future__ import annotations

import time
from decimal import Decimal

from fastapi import APIRouter

from api.db import readonly_conn
from api.envelope import envelope
from api.sources import build_sources

router = APIRouter()


def _fmt_money(x: Decimal | float | int | None) -> str:
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


@router.get("/summary", summary="Portfolio KPIs segmented by property_type")
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


@router.get("/data-quality", summary="Long-form data-quality metrics")
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


@router.get(
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
