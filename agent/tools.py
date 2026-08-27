"""Tool schemas + implementations. One tool per API endpoint in
`docs/api.md` -- no tool invents a query the API doesn't already expose
(CLAUDE.md design rule #2).

Tools call the *running* FastAPI server over HTTP rather than touching the
database directly, so every call inherits PII masking, the `sources` /
`warnings` envelope, and (for the escape hatch) the sqlglot guard for
free. `httpx2` is the vendored `httpx` this environment already installs
transitively via the `anthropic` package -- same API, no new dependency.
"""

from __future__ import annotations

import os
from typing import Any

import httpx2 as httpx

from api.routes import PROPERTY_TYPES


def _api_base_url() -> str:
    return os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")


def _clean(params: dict[str, Any]) -> dict[str, Any]:
    """Drop None values so they don't serialize as the string 'None'."""
    return {k: v for k, v in params.items() if v is not None}


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    resp = httpx.get(f"{_api_base_url()}{path}", params=params, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, json: dict[str, Any]) -> dict[str, Any]:
    resp = httpx.post(f"{_api_base_url()}{path}", json=json, timeout=10.0)
    if resp.status_code == 400:
        # Guard-blocked / validation payload -- still informative to the
        # model, don't raise.
        return resp.json()
    resp.raise_for_status()
    return resp.json()


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "portfolio_summary",
        "description": (
            "Portfolio KPIs segmented by property_type (residential, "
            "affordable, commercial, land, other). Ratios are computed "
            "within each type -- never blend metrics across types."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "portfolio_totals",
        "description": (
            "Portfolio-wide grand totals in a single row: total units, "
            "leases, market/base rent, etc. Use this for 'how many units/"
            "leases in total' questions instead of adding up "
            "portfolio_summary's per-type rows yourself -- that's "
            "computing a number, not reading one. No occupancy percentage "
            "here (a blended portfolio-wide percentage is never valid); "
            "for that, use portfolio_summary or occupancy, per type. "
            "total_units and total_rentable_units can differ -- read the "
            "warning if they do."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "data_quality_summary",
        "description": (
            "Long-form counts of known data-quality issues: audit "
            "failures and unclassified units."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "data_quality_failures",
        "description": (
            "One row per specific data-quality problem (charge_code, "
            "lease_v_units, unclassified_units), each with a "
            "human-readable note explaining exactly what's wrong and why."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_properties",
        "description": "All properties, optionally filtered by property_type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_type": {"type": "string", "enum": list(PROPERTY_TYPES)},
            },
        },
    },
    {
        "name": "property_detail",
        "description": (
            "One property's occupancy (with occupancy_source), charge "
            "mix, delinquency, and loss-to-lease, in a single call."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"property_code": {"type": "string"}},
            "required": ["property_code"],
        },
    },
    {
        "name": "property_leases",
        "description": (
            "Row-level leases for one property. section='current' "
            "(default) is what counts toward occupancy; "
            "section='future' is signed-but-not-moved-in applicants, "
            "excluded from every other metric. Resident names are "
            "already masked."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_code": {"type": "string"},
                "section": {"type": "string", "enum": ["current", "future"]},
                "limit": {"type": "integer"},
                "offset": {"type": "integer"},
            },
            "required": ["property_code"],
        },
    },
    {
        "name": "occupancy",
        "description": (
            "Occupancy per property, carrying occupancy_source "
            "(availability_report or rent_roll_derived) so you know "
            "which report the numerator/denominator came from."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_type": {"type": "string", "enum": list(PROPERTY_TYPES)},
                "property_code": {"type": "string"},
            },
        },
    },
    {
        "name": "loss_to_lease",
        "description": (
            "Market vs effective base rent. Only defined for residential "
            "and affordable properties -- commercial/land/other are out "
            "of scope by design, not a data gap."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_type": {"type": "string", "enum": list(PROPERTY_TYPES)},
                "property_code": {"type": "string"},
            },
        },
    },
    {
        "name": "delinquency",
        "description": "Balances owed per property.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_type": {"type": "string", "enum": list(PROPERTY_TYPES)},
                "property_code": {"type": "string"},
            },
        },
    },
    {
        "name": "charge_mix",
        "description": (
            "Revenue mix by charge category (base_rent, subsidy, "
            "concession, amenity, utility, fee, recovery) per property."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_type": {"type": "string", "enum": list(PROPERTY_TYPES)},
                "property_code": {"type": "string"},
            },
        },
    },
    {
        "name": "expirations",
        "description": (
            "Lease expiration schedule by month, optionally bounded by "
            "from/to ISO dates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_type": {"type": "string", "enum": list(PROPERTY_TYPES)},
                "property_code": {"type": "string"},
                "from": {"type": "string", "description": "ISO date, inclusive"},
                "to": {"type": "string", "description": "ISO date, inclusive"},
            },
        },
    },
    {
        "name": "run_readonly_sql",
        "description": (
            "Last resort only: run a single governed read-only SELECT/CTE "
            "against the gold views when no named tool above covers the "
            "question. Row-capped, function-denylisted, every attempt "
            "audited. Prefer a named tool whenever one applies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string"},
                "question": {
                    "type": "string",
                    "description": "The natural-language question this SQL answers.",
                },
            },
            "required": ["sql"],
        },
    },
]

# Human-readable progress labels for the command dock's live status line
# while a tool call is in flight (agent/client.py's streaming loop).
TOOL_LABELS: dict[str, str] = {
    "portfolio_summary": "Looking up portfolio summary",
    "portfolio_totals": "Looking up portfolio totals",
    "data_quality_summary": "Checking data quality",
    "data_quality_failures": "Checking data quality",
    "list_properties": "Looking up properties",
    "property_detail": "Looking up property metrics",
    "property_leases": "Looking up leases",
    "occupancy": "Looking up occupancy",
    "loss_to_lease": "Looking up loss to lease",
    "delinquency": "Looking up delinquency",
    "charge_mix": "Looking up charge mix",
    "expirations": "Looking up lease expirations",
    "run_readonly_sql": "Running a custom query",
}


def call_tool(name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Dispatch one tool call to its API endpoint. Never raises -- API and
    network failures come back as an `{"error": ...}` payload so the model
    can react (retry, pick another tool, or tell the user) instead of the
    whole turn crashing."""
    try:
        if name == "portfolio_summary":
            return _get("/portfolio/summary")
        if name == "portfolio_totals":
            return _get("/portfolio/totals")
        if name == "data_quality_summary":
            return _get("/portfolio/data-quality")
        if name == "data_quality_failures":
            return _get("/portfolio/data-quality/failures")
        if name == "list_properties":
            return _get("/properties", params=_clean(tool_input))
        if name == "property_detail":
            return _get(f"/properties/{tool_input['property_code']}")
        if name == "property_leases":
            code = tool_input["property_code"]
            params = _clean(
                {k: v for k, v in tool_input.items() if k != "property_code"}
            )
            return _get(f"/properties/{code}/leases", params=params)
        if name == "occupancy":
            return _get("/occupancy", params=_clean(tool_input))
        if name == "loss_to_lease":
            return _get("/loss-to-lease", params=_clean(tool_input))
        if name == "delinquency":
            return _get("/delinquency", params=_clean(tool_input))
        if name == "charge_mix":
            return _get("/charge-mix", params=_clean(tool_input))
        if name == "expirations":
            return _get("/expirations", params=_clean(tool_input))
        if name == "run_readonly_sql":
            return _post(
                "/run-readonly-sql",
                json={
                    "sql": tool_input["sql"],
                    "question": tool_input.get("question"),
                },
            )
        return {"error": f"unknown tool {name!r}"}
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json()
        except ValueError:
            detail = exc.response.text
        return {"error": f"API returned {exc.response.status_code}", "detail": detail}
    except httpx.RequestError as exc:
        return {"error": f"could not reach API: {exc}"}
