"""Numeric grounding check (CLAUDE.md design rule #1): every figure the
model states must have actually appeared in a tool result. This is a
heuristic post-check on rendered text, not a proof -- it catches the
common failure (the model computing or misremembering a number), and the
fail-closed path in `agent/run.py` is what makes that acceptable.

Numbers are pulled from both structured tool-result values *and* the
prose inside them (e.g. a `warnings[].message` string that already says
"7 properties") -- an API-authored note is a legitimate source for a
figure, not just raw JSON numbers.
"""

from __future__ import annotations

import re
from typing import Any

_CURRENCY_RE = re.compile(r"\$\s?-?\d[\d,]*(?:\.\d+)?")
_PERCENT_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?\s?%")
_PLAIN_RE = re.compile(r"(?<![\w.$])-?\d[\d,]*(?:\.\d+)?(?!\w)")

# Absolute tolerance for float comparison -- covers cent-level rounding
# when the model drops trailing zeros ("$754,322" vs. 754322.0).
_TOLERANCE = 0.02


def _normalize(token: str) -> float | None:
    cleaned = token.replace("$", "").replace("%", "").replace(",", "").strip()
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def extract_numbers(text: str) -> set[float]:
    """Every number-like token in `text`, normalized. Bare four-digit
    values that read as a calendar year (1900-2100) are excluded -- those
    are almost always prose ("as of 2026-02-25"), not a computed figure,
    and the actual as_of_date is grounded separately via `sources`.

    Currency/percent spans are matched first and masked out before the
    plain-number pass -- otherwise `$3,012` also yields a spurious `012`
    (-> 12.0) from re-entering the digits after the internal comma.

    Every `pct_*` field in this API is a 0-1 fraction (`v_occupancy_by_
    property.pct_occupied`, etc. -- see `db/migrations/004_gold_views.sql`
    and `dashboard-app/src/lib/format.ts`'s `pct()`, which multiplies by
    100 to display). A model correctly stating "78.15%" is claiming the
    fraction 0.7815, so percent matches are divided by 100 here -- without
    this, a *correct* percentage answer fails grounding (0.7815 vs. the
    literal 78.15), while a wrong one 100x off ("0.78%") would pass.
    """
    found: set[float] = set()
    masked = text
    for match in _CURRENCY_RE.finditer(text):
        value = _normalize(match.group())
        if value is not None:
            found.add(value)
    for match in _PERCENT_RE.finditer(text):
        value = _normalize(match.group())
        if value is not None:
            found.add(round(value / 100, 4))
    for pattern in (_CURRENCY_RE, _PERCENT_RE):
        masked = pattern.sub(lambda m: " " * len(m.group()), masked)

    for match in _PLAIN_RE.finditer(masked):
        value = _normalize(match.group())
        if value is None:
            continue
        if 1900 <= value <= 2100 and value == int(value):
            continue
        found.add(value)
    return found


def _flatten_numbers(obj: Any, *, key: str | None = None) -> set[float]:
    """Recurse through a tool result collecting numbers.

    `snapshot_id`/`property_id`/`lease_id`/etc. are internal identifiers,
    not data figures -- with 25 properties and thousands of leases, small
    identifiers like `1`, `5`, `11` coincidentally overlap with legitimate
    counts (e.g. `n_properties`), which would let a miscounted answer look
    "grounded" just because some row's id happened to match. Skip any
    `*_id` field so an identifier can never stand in for a real figure.
    """
    found: set[float] = set()
    if isinstance(obj, bool):
        return found
    if key is not None and (key == "id" or key.endswith("_id")):
        return found
    if isinstance(obj, (int, float)):
        found.add(round(float(obj), 2))
    elif isinstance(obj, str):
        found |= extract_numbers(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            found |= _flatten_numbers(v, key=k)
    elif isinstance(obj, list):
        for v in obj:
            found |= _flatten_numbers(v, key=key)
    return found


def grounded_numbers(tool_results: list[dict[str, Any]]) -> set[float]:
    """Every number available anywhere across this turn's tool results."""
    found: set[float] = set()
    for result in tool_results:
        found |= _flatten_numbers(result)
    return found


def find_ungrounded(
    answer_text: str,
    tool_results: list[dict[str, Any]],
    *,
    tolerance: float = _TOLERANCE,
) -> list[float]:
    """Numbers stated in `answer_text` that don't match any number
    available in `tool_results`, within `tolerance`. Empty list means the
    answer is fully grounded."""
    available = grounded_numbers(tool_results)
    ungrounded = []
    for value in extract_numbers(answer_text):
        if not any(abs(value - g) <= tolerance for g in available):
            ungrounded.append(value)
    return ungrounded
