"""Parser for 'Rent Roll with Lease Charges'.

The file is not a table. It is a sequence of lease blocks:

    A103 | 115mxA05 | 755 | t0019683 | Resident 1 | 2472 | RENT | 2480 | ...
         |          |     |          |            |      | PETFEEM | 50
         |          |     |          |            |      | AMENITY | 40
         |          |     |          |            |      | Total   | 2760
                                                                            <- blank

So the parser is a stateful row classifier, not a read_excel call. Two
properties of the format are easy to get wrong:

  1. The lease's FIRST charge sits on the lease row itself (columns 6-7).
     Collecting only sub-rows silently drops one charge per lease.
  2. Charge order is not fixed -- some leases lead with PARKING and place
     RENT third -- so column 6 cannot be assumed to be base rent.
"""

from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from ..models import ChargeRecord, FileHeader, LeaseRecord
from ..normalize import to_date, to_int, to_money, to_text
from .helpers import cell, parse_header, text_at

# Column positions, from the joined two-row header at rows 4-5.
UNIT = 0
UNIT_TYPE = 1
SQFT = 2
RESIDENT = 3
NAME = 4
MARKET_RENT = 5
CHARGE_CODE = 6
AMOUNT = 7
RESIDENT_DEPOSIT = 8
OTHER_DEPOSIT = 9
MOVE_IN = 10
LEASE_EXPIRATION = 11
MOVE_OUT = 12
BALANCE = 13

SECTIONS = {
    "Current/Notice/Vacant Residents": "current",
    "Future Residents/Applicants": "future",
}
VACANT = "VACANT"
TOTAL = "Total"


def parse_rent_roll(path: Path) -> tuple[FileHeader, list[LeaseRecord], list[str]]:
    """Return (header, leases, warnings). Never raises on a single bad row."""
    df = pd.read_excel(path, header=None)
    header = parse_header(df, path)

    leases: list[LeaseRecord] = []
    warnings: list[str] = []
    section: str | None = None
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        try:
            leases.append(LeaseRecord(**current))
        except Exception as exc:                      # noqa: BLE001
            warnings.append(f"row {current['source_row']}: {exc}")
        current = None

    for row in range(len(df)):
        first = text_at(df, row, UNIT)

        # The summary blocks repeat the section names, so stop here.
        if first and first.startswith("Summary"):
            break
        if first in SECTIONS:
            flush()
            section = SECTIONS[first]
            continue
        if section is None or first == "Totals:":
            continue

        code = text_at(df, row, CHARGE_CODE)
        unit_type = text_at(df, row, UNIT_TYPE)

        # A lease row has both a unit number and a unit type.
        if first and unit_type:
            flush()
            is_vacant = text_at(df, row, RESIDENT) == VACANT
            current = dict(
                section=section,
                unit_number=first,
                unit_type=unit_type,
                square_feet=to_int(cell(df, row, SQFT)),
                resident_code=None if is_vacant else text_at(df, row, RESIDENT),
                resident_name=None if is_vacant else text_at(df, row, NAME),
                is_vacant=is_vacant,
                market_rent=to_money(cell(df, row, MARKET_RENT)),
                resident_deposit=to_money(cell(df, row, RESIDENT_DEPOSIT)),
                other_deposit=to_money(cell(df, row, OTHER_DEPOSIT)),
                balance=to_money(cell(df, row, BALANCE)),
                move_in_date=to_date(cell(df, row, MOVE_IN)),
                lease_expiration=to_date(cell(df, row, LEASE_EXPIRATION)),
                move_out_date=to_date(cell(df, row, MOVE_OUT)),
                charges=[],
                source_row=row,
            )
            # The first charge lives on the lease row itself.
            if code and code != TOTAL:
                amount = to_money(cell(df, row, AMOUNT))
                if amount is not None:
                    current["charges"].append(ChargeRecord(
                        charge_code=code.upper(), amount=amount, source_row=row))

        elif not first and code and current is not None:
            # Each block ends with its own Total: the reconciliation target.
            if code == TOTAL:
                current["reported_total"] = to_money(cell(df, row, AMOUNT))
            else:
                amount = to_money(cell(df, row, AMOUNT))
                if amount is None:
                    warnings.append(f"row {row}: charge {code} has no amount")
                else:
                    current["charges"].append(ChargeRecord(
                        charge_code=code.upper(), amount=amount, source_row=row))

        elif first and not unit_type and first != TOTAL:
            warnings.append(f"row {row}: unclassified row {first!r}")

    flush()
    return header, leases, warnings


def parse_charge_summary(path: Path) -> dict[str, object] | None:
    """The 'Summary of Charges by Charge Code' block, when present.

    Only 16 of 25 files carry it, so this is a secondary cross-check on top
    of the per-lease totals.
    """
    df = pd.read_excel(path, header=None)

    start = None
    for row in range(len(df)):
        if text_at(df, row, 0) == "Charge Code":
            start = row + 1
            break
    if start is None:
        return None

    totals: dict[str, object] = {}
    for row in range(start, len(df)):
        code = text_at(df, row, 0)
        if not code:
            continue
        amount = to_money(cell(df, row, 3))
        if code == TOTAL:
            totals["__TOTAL__"] = amount
            break
        totals[code.upper()] = amount
    return totals