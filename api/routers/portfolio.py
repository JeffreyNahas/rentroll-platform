"""Portfolio-wide rollups. No filters -- these views are the top of the
dashboard and always show the whole book."""

from __future__ import annotations

import time

from fastapi import APIRouter

from api.db import readonly_conn
from api.envelope import envelope
from api.sources import build_sources

router = APIRouter()


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
    """Backs the dashboard's data-quality panel. Long form
    (`metric_name` / `value`) so we can add metrics without a migration."""
    started = time.perf_counter()
    with readonly_conn() as conn:
        rows = conn.execute("""
            SELECT metric_name, value FROM v_data_quality_summary
        """).fetchall()
        sources = build_sources(conn)
    return envelope(rows, sources, started)
