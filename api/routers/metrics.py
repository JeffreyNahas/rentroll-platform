"""Metric endpoints: one per gold view.

Every endpoint accepts optional `property_type` and (where meaningful)
`property_code` filters. The response's `sources` list narrows to the
files whose rows contributed -- so a `?property_code=115r` call cites
exactly the two 115r files.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from psycopg import Connection

from api.db import readonly_conn
from api.envelope import ApiWarning, envelope
from api.sources import build_sources

router = APIRouter()

PROPERTY_TYPES = ("residential", "affordable", "commercial", "land", "other")
LTL_TYPES_IN_SCOPE = frozenset({"residential", "affordable"})


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


# ── occupancy ─────────────────────────────────────────────────────────────
@router.get("/occupancy", summary="Occupancy per property, with occupancy_source")
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


# ── loss to lease ────────────────────────────────────────────────────────
@router.get("/loss-to-lease", summary="Market vs effective base rent")
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


# ── delinquency ──────────────────────────────────────────────────────────
@router.get("/delinquency", summary="Balances owed per property")
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


# ── charge mix ───────────────────────────────────────────────────────────
@router.get("/charge-mix", summary="Revenue mix by charge category")
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


# ── expirations ──────────────────────────────────────────────────────────
@router.get("/expirations", summary="Lease expiration schedule by month")
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
