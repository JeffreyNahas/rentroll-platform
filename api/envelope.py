"""Response envelope and provenance types.

Every query response has the same shape:

    {"data": [...], "sources": [...], "row_count": N,
     "query_time_ms": M, "warnings": []}

`sources` is the honest answer to "where did this number come from" -- a
list of the exact snapshots (and therefore files) whose rows contributed.
For portfolio endpoints that's up to 50 entries; for property-scoped
endpoints, typically 2. `run_readonly_sql` returns `sources: null` plus a
warning entry because arbitrary SQL can touch anything.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


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
