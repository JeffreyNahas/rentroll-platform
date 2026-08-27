"""Check that all 50 source files match the structure we expect.

We inspected one file from each family by hand, then ran this across the whole
set. Findings from that first run are baked in below:

  - Not every property has a "Future Residents" section, so one section is fine.
  - Some properties (land, management entities) have no leases at all.
  - Total units = the five occupancy states PLUS model/down/admin units,
    which are non-revenue and excluded from the states.
  - The portfolio is mixed-use: property codes end in r (residential),
    a (affordable), c (commercial), or name a land/management entity.
    Each type uses a different set of charge codes.

Reports problems instead of crashing. Writes nothing to the database.

    python scripts/discover.py
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The column-header expectations live in ingest/parsers/helpers.py -- the
# same place `check_columns` enforces them at load time -- so this
# diagnostic and the actual parsers can never drift apart on what a
# well-formed file looks like.
from ingest.parsers.helpers import EXPECTED_COLUMNS as EXPECTED
from ingest.parsers.helpers import read_headers

RAW = Path("data/raw")

FOLDERS = {
    "rent_roll": "Rent_Roll_with_Lease_Charges",
    "unit_availability": "Unit_Availability",
}

KNOWN_SECTIONS = {"Current/Notice/Vacant Residents", "Future Residents/Applicants"}

# Availability column positions
UNITS_COL = 4
STATE_COLS = range(5, 10)      # occupied no notice, vacant x2, notice x2
NONREV_COLS = range(11, 14)    # model, down, admin


def text(df: pd.DataFrame, row: int, col: int) -> str | None:
    """Read a cell as a stripped string, or None if it's empty."""
    if row >= len(df) or col >= df.shape[1]:
        return None
    value = df.iat[row, col]
    return None if pd.isna(value) else str(value).strip()


def read_title(df: pd.DataFrame) -> tuple[str | None, str | None, str | None]:
    """Rows 0-3 hold 'Property Name (code)' and 'As Of = date'."""
    name = code = as_of = None
    for row in range(5):
        line = text(df, row, 0)
        if not line:
            continue
        match = re.match(r"^(.*?)\s*\(([^)]+)\)$", line)
        if match and "Rent Roll" not in line and "Unit Availability" not in line:
            name, code = match.groups()
        if match := re.search(r"As Of\s*=\s*(\S+)", line):
            as_of = match.group(1)
    return name, code, as_of


def property_type(code: str | None) -> str:
    """The code suffix tells us the property type, which drives everything else."""
    if not code:
        return "unknown"
    if code.endswith("r"):
        return "residential"
    if code.endswith("a"):
        return "affordable"
    if code.endswith("c"):
        return "commercial"
    if "land" in code:
        return "land"
    return "other"


def check_rent_roll(df: pd.DataFrame) -> tuple[dict[str, Any], list[str], list[str]]:
    """Count leases and collect charge codes.

    Returns (findings, problems, notes). Notes are expected variations;
    problems are things that would break the parser.
    """
    leases = {"current": 0, "future": 0}
    vacant = 0
    lease_totals = 0          # lease blocks that end with a "Total" row
    codes = set()
    sections = []
    has_summary = False
    section = None

    for row in range(len(df)):
        first = text(df, row, 0)

        # The summary blocks at the bottom repeat the section names,
        # so stop reading lease data as soon as we reach them.
        if first and first.startswith("Summary"):
            if "Charges by Charge Code" in first:
                has_summary = True
            break
        if first in KNOWN_SECTIONS:
            sections.append(first)
            section = "current" if first.startswith("Current") else "future"
            continue
        if section is None or first == "Totals:":
            continue

        code = text(df, row, 6)

        # A lease row has both a unit number and a unit type.
        # Its first charge sits on that same row, not below it.
        if first and text(df, row, 1):
            leases[section] += 1
            if text(df, row, 3) == "VACANT":
                vacant += 1
            if code and code != "Total":
                codes.add(code.upper())
        # Each lease block ends with a "Total" row -- our fallback
        # reconciliation target, present even when the file-level
        # charge summary is missing.
        elif not first and code == "Total":
            lease_totals += 1
        # A charge row has a code but no unit number.
        elif not first and code:
            codes.add(code.upper())

    # Look for the summary block again in case we never hit the break above
    # (an empty rent roll has no lease rows to scan past).
    if not has_summary:
        has_summary = any(
            (t := text(df, r, 0)) and t.startswith("Summary of Charges")
            for r in range(len(df))
        )

    total_leases = leases["current"] + leases["future"]
    problems, notes = [], []

    if not sections and total_leases:
        problems.append("lease rows found but no section header")
    # Every lease block should end with a Total row. If they don't match,
    # the per-lease reconciliation fallback won't cover this file.
    if total_leases and lease_totals != total_leases:
        problems.append(f"{lease_totals} lease-total rows for {total_leases} "
                        "leases -- per-lease reconciliation incomplete")

    if total_leases == 0:
        notes.append(f"no leases ({len(df)} rows total) -- expected for land "
                     "and management entities")
    if not has_summary and total_leases:
        notes.append("no file-level charge summary -- falling back to "
                     f"{lease_totals} per-lease totals")

    return ({"leases_current": leases["current"], "leases_future": leases["future"],
             "vacant": vacant, "codes": codes, "lease_totals": lease_totals,
             "file_summary": has_summary}, problems, notes)


def check_availability(df: pd.DataFrame) -> tuple[dict[str, Any], list[str], list[str]]:
    """This report is one summary row per property, not one row per unit."""
    problems, notes = [], []

    units = df.iat[5, UNITS_COL]
    states = [df.iat[5, c] for c in STATE_COLS]
    nonrev = [df.iat[5, c] for c in NONREV_COLS]

    # Every unit is in one of five states, or is non-revenue (model, down,
    # admin). If these don't add up, the two-row header was joined wrong
    # and every field after it is shifted.
    if sum(states) + sum(nonrev) != units:
        gap = units - sum(states) - sum(nonrev)
        populated = {c: df.iat[5, c] for c in range(4, df.shape[1])
                     if pd.notna(df.iat[5, c]) and df.iat[5, c] != 0}
        problems.append(
            f"states {sum(states):g} + non-revenue {sum(nonrev):g} != Units "
            f"{units:g} (gap {gap:g}); populated cols {populated}"
        )
    elif sum(nonrev):
        notes.append(f"{sum(nonrev):g} non-revenue units "
                     "(excluded from the occupancy denominator)")

    vacant = states[1] + states[2]
    return ({"units": units, "vacant": vacant,
             "nonrev": sum(nonrev)}, problems, notes)


def main() -> None:
    codes_by_type: dict[str, set[str]] = defaultdict(set)
    property_codes: dict[str, set[str | None]] = {
        "rent_roll": set(),
        "unit_availability": set(),
    }
    types: dict[str | None, str] = {}
    totals: dict[str, float] = defaultdict(float)
    no_summary = []
    n_problems = n_notes = 0

    for family, (header_rows, expected_columns) in EXPECTED.items():
        folder = RAW / FOLDERS[family]
        files = sorted(p for p in folder.glob("*.xls*")
                       if not p.name.startswith("~$"))
        print(f"\n{family}: {len(files)} files in {folder}")

        for path in files:
            df = pd.read_excel(path, header=None)
            problems, notes = [], []

            columns = read_headers(df, header_rows)
            if columns[:len(expected_columns)] != expected_columns:
                problems.append(f"unexpected columns: {columns[:len(expected_columns)]}")

            _name, code, as_of = read_title(df)
            if not code:
                problems.append("no property code in title")
            if not as_of:
                problems.append("no as-of date in title")
            property_codes[family].add(code)
            ptype = property_type(code)
            types[code] = ptype

            if family == "rent_roll":
                found, more_p, more_n = check_rent_roll(df)
                codes_by_type[ptype] |= found["codes"]
                totals["leases_current"] += found["leases_current"]
                totals["leases_future"] += found["leases_future"]
                totals["vacant"] += found["vacant"]
                totals["lease_totals"] += found["lease_totals"]
                totals["file_summary"] += found["file_summary"]
                if not found["file_summary"] and found["leases_current"]:
                    no_summary.append(code)
            else:
                found, more_p, more_n = check_availability(df)
                totals["units"] += found["units"]
                totals["nonrev"] += found["nonrev"]

            problems += more_p
            notes += more_n
            n_problems += len(problems)
            n_notes += len(notes)

            status = "PROBLEM" if problems else ("note" if notes else "OK")
            print(f"  [{status:>7}] {code or '?':<8} {ptype:<12} {path.name}")
            for item in problems:
                print(f"            ! {item}")
            for item in notes:
                print(f"            - {item}")

    print("\n" + "=" * 70)
    print("PORTFOLIO")
    print("=" * 70)
    by_type = defaultdict(list)
    for code, ptype in types.items():
        by_type[ptype].append(code)
    for ptype, codes in sorted(by_type.items()):
        print(f"  {ptype:<12} {len(codes):>2}  {sorted(codes)}")

    print("\n" + "=" * 70)
    print("CHARGE CODES BY PROPERTY TYPE")
    print("=" * 70)
    for ptype, codes in sorted(codes_by_type.items()):
        print(f"  {ptype:<12} {len(codes):>2}  {sorted(codes)}")
    populated = [c for c in codes_by_type.values() if c]
    shared = set.intersection(*populated) if populated else set()
    print(f"\n  shared by every type that has leases: {sorted(shared)}")

    print("\n" + "=" * 70)
    print("TOTALS")
    print("=" * 70)
    n_files = len(property_codes["rent_roll"])
    print(f"  current leases {totals['leases_current']:.0f}   "
          f"future applicants {totals['leases_future']:.0f}   "
          f"vacant {totals['vacant']:.0f}")
    print(f"  units {totals['units']:.0f}   non-revenue {totals['nonrev']:.0f}")

    print("\n  RECONCILIATION COVERAGE")
    print(f"    per-lease totals:   {totals['lease_totals']:.0f} checks "
          f"across {n_files} files")
    print(f"    file-level summary: {totals['file_summary']:.0f}/{n_files} files")
    if no_summary:
        print(f"    no file summary (per-lease only): {sorted(no_summary)}")

    # Current leases should equal units: both reports counting the same thing.
    delta = totals["leases_current"] - totals["units"]
    if delta:
        print(f"    NOTE: current leases - units = {delta:.0f} "
              "(investigate before trusting portfolio occupancy)")
    else:
        print("    current leases == units: rent roll and availability agree")

    only_rr = property_codes["rent_roll"] - property_codes["unit_availability"]
    only_ua = property_codes["unit_availability"] - property_codes["rent_roll"]
    if only_rr or only_ua:
        print(f"  property codes DO NOT match: rent_roll only {only_rr}, "
              f"availability only {only_ua}")
    else:
        print("  property codes match across both families")

    print(f"\n  {n_problems} problem(s), {n_notes} note(s)")


if __name__ == "__main__":
    main()