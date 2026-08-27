"""Response envelope: citations, warnings, PII masking.

Every query response has the same shape:

    {"data": [...], "sources": [...], "row_count": N,
     "query_time_ms": M, "warnings": []}

`sources` is the honest answer to "where did this number come from" -- a
list of the exact snapshots (and therefore files) whose rows contributed.
For portfolio endpoints that's up to 50 entries; for property-scoped
endpoints, typically 2. `run_readonly_sql` returns `sources: null` plus a
warning entry because arbitrary SQL can touch anything.

PII: storage stays unmasked (`resident.display_name`); masking is a
boundary concern. With `MASK_PII=true` (default), lease rows substitute
`Resident #<resident_id>`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from psycopg import Connection


def _decimals_to_floats(obj: Any) -> Any:
    """Walk `obj` and coerce every Decimal to float in place.

    Pydantic v2 / FastAPI serialize Decimal to string by default. That's
    precision-safe, but every downstream number becomes `"731492.00"`
    instead of `731492.00`, forcing every JS/Python client to parse.
    Currency here is at worst 10 digits before the decimal + 2 after -- well
    within float64's ~15 digits of precision -- so the safer default for
    this API is: strings out, numbers back."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimals_to_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimals_to_floats(v) for v in obj]
    return obj


@dataclass
class Source:
    snapshot_id: int
    property_code: str
    report_type: str            # 'rent_roll' | 'unit_availability'
    filename: str
    as_of_date: date


@dataclass
class ApiWarning:
    code: str
    message: str


def envelope(
    data: list[dict[str, Any]],
    sources: list[Source] | None,
    started_at: float,
    warnings: list[ApiWarning] | None = None,
) -> dict[str, Any]:
    """Serialisable envelope. FastAPI's default JSON encoder handles the
    dataclasses, date/datetime, and Decimal all on its own."""
    return {
        "data": _decimals_to_floats(data),
        "sources": sources,
        "row_count": len(data),
        "query_time_ms": int((time.perf_counter() - started_at) * 1000),
        "warnings": warnings or [],
    }


def build_sources(
    conn: Connection,
    property_codes: list[str] | None = None,
    report_types: list[str] | None = None,
) -> list[Source]:
    """Return one Source per (property, report_type) at the latest snapshot.

    `property_codes=None` (default) returns sources for every property.
    Sources always point at the *latest* snapshot per (property, report_type)
    -- the same rule the gold views apply -- so citations stay consistent
    with the numbers they explain.
    """
    where: list[str] = []
    params: list = []
    if property_codes:
        where.append("p.property_code = ANY(%s)")
        params.append(property_codes)
    if report_types:
        where.append("rs.report_type = ANY(%s)")
        params.append(report_types)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT DISTINCT ON (rs.property_id, rs.report_type)
            rs.snapshot_id,
            p.property_code,
            rs.report_type,
            sf.filename,
            rs.as_of_date
        FROM report_snapshot rs
        JOIN property p     ON p.property_id     = rs.property_id
        JOIN source_file sf ON sf.source_file_id = rs.source_file_id
        {where_sql}
        ORDER BY rs.property_id, rs.report_type, rs.as_of_date DESC
    """
    rows = conn.execute(sql, params).fetchall()
    return [
        Source(
            snapshot_id=r["snapshot_id"],
            property_code=r["property_code"],
            report_type=r["report_type"],
            filename=r["filename"],
            as_of_date=r["as_of_date"],
        )
        for r in rows
    ]


def mask_display_name(
    row: dict[str, Any],
    *,
    mask: bool,
    name_field: str = "display_name",
    id_field: str = "resident_id",
) -> dict[str, Any]:
    """Return `row` with the name field replaced if masking is on.

    Mutates the row in place and returns it -- convenient for list
    comprehensions.
    """
    if not mask:
        return row
    if row.get(name_field) is None:
        return row
    resident_id = row.get(id_field)
    row[name_field] = (
        f"Resident #{resident_id}" if resident_id is not None else "Resident (unknown)"
    )
    return row
