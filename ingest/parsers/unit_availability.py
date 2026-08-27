"""Parser for 'Unit Availability'.

This report is a PROPERTY-LEVEL rollup: one data row per file, not one row
per unit. It is loaded as an independent control total to validate the rent
roll against, not as a second unit-grained source.

The header wraps across rows 3-4: row 3 holds 'Occupied' and row 4 holds
'No Notice', which together are one column. Reading either row alone shifts
every field after it.
"""

from pathlib import Path

import pandas as pd

from ..models import AvailabilityRecord, FileHeader
from ..normalize import to_int, to_money
from .helpers import cell, check_columns, parse_header, text_at

DATA_ROW = 5

# Joined header positions
UNITS = 4
OCCUPIED_NO_NOTICE = 5
VACANT_RENTED = 6
VACANT_UNRENTED = 7
NOTICE_RENTED = 8
NOTICE_UNRENTED = 9
AVAILABLE = 10
MODEL = 11
DOWN = 12
ADMIN = 13


def parse_availability(path: Path) -> tuple[FileHeader, AvailabilityRecord]:
    df = pd.read_excel(path, header=None)
    header = parse_header(df, path)
    check_columns(df, path, "unit_availability")

    def count(col: int) -> int:
        return to_int(cell(df, DATA_ROW, col)) or 0

    record = AvailabilityRecord(
        property_code=text_at(df, DATA_ROW, 0) or header.property_code,
        property_name=text_at(df, DATA_ROW, 1) or header.property_name,
        avg_square_feet=to_int(cell(df, DATA_ROW, 2)),
        avg_rent=to_money(cell(df, DATA_ROW, 3)),
        total_units=count(UNITS),
        occupied_no_notice=count(OCCUPIED_NO_NOTICE),
        vacant_rented=count(VACANT_RENTED),
        vacant_unrented=count(VACANT_UNRENTED),
        notice_rented=count(NOTICE_RENTED),
        notice_unrented=count(NOTICE_UNRENTED),
        available=count(AVAILABLE),
        model_units=count(MODEL),
        down_units=count(DOWN),
        admin_units=count(ADMIN),
        pct_occupied=to_money(cell(df, DATA_ROW, 14)),
        pct_occupied_nonrev=to_money(cell(df, DATA_ROW, 15)),
        pct_leased=to_money(cell(df, DATA_ROW, 16)),
        pct_trend=to_money(cell(df, DATA_ROW, 17)),
        source_row=DATA_ROW,
    )
    return header, record