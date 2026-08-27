"""Shared helpers for reading the report title block and validating its
column layout."""

import re
from pathlib import Path

import pandas as pd

from ..models import FileHeader
from ..normalize import to_date, to_text

_PROPERTY = re.compile(r"^(?P<name>.*?)\s*\((?P<code>[^)]+)\)\s*$")
_AS_OF = re.compile(r"As Of\s*=\s*(?P<date>\S+)", re.IGNORECASE)

TITLES = ("Rent Roll", "Unit Availability")

# Both parsers read data cells by fixed column index (UNIT=0, CHARGE_CODE=6,
# etc. in rent_roll.py; UNITS=4, MODEL=11, etc. in unit_availability.py).
# Nothing about that indexing checks itself against the file's actual
# headers -- a shifted or renamed column would silently load the wrong
# value into the wrong field. That's worse than a crash: it can still
# pass Total-row reconciliation by coincidence and land in the database
# looking correct. `check_columns` below is the guard; the expected
# layouts here are also `scripts/discover.py`'s only source of truth for
# the same check, so the two can't drift apart.
EXPECTED_COLUMNS: dict[str, tuple[tuple[int, int], list[str]]] = {
    "rent_roll": (
        (4, 5),  # header rows to join
        ["Unit", "Unit Type", "Unit Sq Ft", "Resident", "Name", "Market Rent",
         "Charge Code", "Amount", "Resident Deposit", "Other Deposit",
         "Move In", "Lease Expiration", "Move Out", "Balance"],
    ),
    "unit_availability": (
        (3, 4),
        ["Property", "Name", "Avg. Sq Ft", "Avg. Rent", "Units",
         "Occupied No Notice", "Vacant Rented", "Vacant Unrented",
         "Notice Rented", "Notice Unrented", "Avail", "Model", "Down",
         "Admin", "% Occ", "% Occ w/NonRev", "% Leased", "% Trend"],
    ),
}


def cell(df: pd.DataFrame, row: int, col: int):
    """Raw cell value, or None if out of bounds or empty."""
    if row >= len(df) or col >= df.shape[1]:
        return None
    value = df.iat[row, col]
    return None if pd.isna(value) else value


def text_at(df: pd.DataFrame, row: int, col: int) -> str | None:
    return to_text(cell(df, row, col))


def read_headers(df: pd.DataFrame, rows: tuple[int, int]) -> list[str]:
    """Join the two header rows into one label per column (e.g. 'Occupied'
    over 'No Notice' becomes one 'Occupied No Notice' column)."""
    top, bottom = rows
    return [
        f"{text_at(df, top, c) or ''} {text_at(df, bottom, c) or ''}".strip()
        for c in range(df.shape[1])
    ]


def check_columns(df: pd.DataFrame, path: Path, report_type: str) -> None:
    """Raise if the file's header doesn't match the fixed column layout
    every parser reads by index -- see `EXPECTED_COLUMNS` above for why
    this matters. Called right after `parse_header` in both parsers, so
    a shifted file fails here, loudly, before a single data cell is read."""
    header_rows, expected = EXPECTED_COLUMNS[report_type]
    actual = read_headers(df, header_rows)[: len(expected)]
    if actual != expected:
        raise ValueError(
            f"{path.name}: unexpected column headers -- the parser reads "
            f"fixed positions and cannot trust this file's layout. "
            f"expected {expected}, got {actual}"
        )


def parse_header(df: pd.DataFrame, path: Path) -> FileHeader:
    """Rows 0-3 hold the report title, 'Property Name (code)', and 'As Of'."""
    name = code = as_of = None

    for row in range(6):
        line = text_at(df, row, 0)
        if not line:
            continue
        if (match := _PROPERTY.match(line)) and not any(t in line for t in TITLES):
            name, code = match.group("name"), match.group("code")
        if match := _AS_OF.search(line):
            as_of = to_date(match.group("date"))

    if not code:
        raise ValueError(f"{path.name}: no 'Property Name (code)' line in the title block")
    if not as_of:
        raise ValueError(f"{path.name}: no 'As Of' date in the title block")

    return FileHeader(property_code=code, property_name=name or code, as_of_date=as_of)