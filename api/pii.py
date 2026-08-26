"""PII masking, applied at response-serialisation time.

Storage stays unmasked (`resident.display_name`); masking is a boundary
concern. With `MASK_PII=true` (default), any endpoint returning names
substitutes `Resident #<resident_id>` -- stable across responses so a
follow-up question about "resident 4821" is still meaningful.
"""

from __future__ import annotations

from typing import Any


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
