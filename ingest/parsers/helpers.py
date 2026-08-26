"""Shared helpers for reading the report title block."""

import re
from pathlib import Path

import pandas as pd

from ..models import FileHeader
from ..normalize import to_date, to_text

_PROPERTY = re.compile(r"^(?P<name>.*?)\s*\((?P<code>[^)]+)\)\s*$")
_AS_OF = re.compile(r"As Of\s*=\s*(?P<date>\S+)", re.I)

TITLES = ("Rent Roll", "Unit Availability")


def cell(df: pd.DataFrame, row: int, col: int):
    """Raw cell value, or None if out of bounds or empty."""
    if row >= len(df) or col >= df.shape[1]:
        return None
    value = df.iat[row, col]
    return None if pd.isna(value) else value


def text_at(df: pd.DataFrame, row: int, col: int) -> str | None:
    return to_text(cell(df, row, col))


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