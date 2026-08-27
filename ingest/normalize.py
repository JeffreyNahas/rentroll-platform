"""Type coercion for values read out of the source spreadsheets.

Small and boring on purpose: these are the functions that turn Yardi's
display formatting back into data, and getting any of them wrong corrupts
every downstream number silently.
"""

import math
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

# Yardi renders credits as (1,234.56) rather than -1234.56
_PARENS = re.compile(r"^\((.*)\)$")
_BLANK = {"", "-", "--", "n/a", "na", "none", "nan"}

_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
    "%m/%d/%Y", "%m/%d/%y",
    "%d-%b-%Y", "%m/%d/%Y %H:%M:%S",
)


def to_money(value) -> Decimal | None:
    """Parse a currency cell. Returns None for blanks, never raises."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = (str(value).strip()
            .replace("$", "").replace(",", "").replace("\u00a0", ""))
    if text.lower() in _BLANK:
        return None
    if match := _PARENS.match(text):
        text = "-" + match.group(1)
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def to_date(value) -> date | None:
    """Parse a date cell. Handles real datetimes, Excel serials, and strings."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    # Excel stores dates as days since 1899-12-30. Naive datetimes are
    # correct here, not an oversight: the source is a calendar date with
    # no time-of-day or timezone component, and `.date()` discards
    # whatever naive time this constructs anyway.
    if isinstance(value, (int, float)) and 20_000 < value < 60_000:
        return (datetime(1899, 12, 30) + timedelta(days=int(value))).date()  # noqa: DTZ001

    text = str(value).strip()
    if text.lower() in _BLANK:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()  # noqa: DTZ007
        except ValueError:
            continue
    return None


def to_int(value) -> int | None:
    money = to_money(value)
    return None if money is None else int(money)


def to_text(value) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    return None if text.lower() in _BLANK else text


def property_type(property_code: str) -> str:
    """The property code suffix encodes the asset type.

    This drives which charge codes count as rent and how occupancy is
    computed, so it is derived once here rather than inferred per query.
    """
    code = property_code.lower()
    if "land" in code:
        return "land"
    if code.endswith("r"):
        return "residential"
    if code.endswith("a"):
        return "affordable"
    if code.endswith("c"):
        return "commercial"
    return "other"