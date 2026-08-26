"""Property-centric endpoints.

`/properties/{code}/leases` is the row-level drill-down. It's the only
endpoint that touches resident names, so PII masking (`MASK_PII` env var)
runs here.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query

from api.config import settings
from api.db import readonly_conn
from api.envelope import ApiWarning, envelope
from api.pii import mask_display_name
from api.sources import build_sources

router = APIRouter()

LEASE_SECTIONS = ("current", "future")


@router.get("", summary="All properties (no snapshot data)")
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


@router.get("/{code}", summary="One property: occupancy + charge mix")
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


@router.get("/{code}/leases", summary="Lease detail for a property")
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
