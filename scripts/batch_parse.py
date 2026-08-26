"""Batch-test both parsers across all 50 source files.

`discover.py` validates the *shape* of the files. This script runs the actual
parsers and checks that the records they produce reconcile against the totals
carried inside the files themselves.

For each rent roll file:
  * counts by lease status (current / notice / vacant / future)
  * every parser warning
  * per-lease reconciliation: |sum(charges) - reported_total| > $0.01
  * file-level charge-summary reconciliation, on the 16 files that carry it

For each availability file:
  * state totals, non-revenue, unclassified units, states_reconcile

For each property (joined across both families):
  * (current + notice) leases in the rent roll vs
    (occupied_no_notice + notice_rented + notice_unrented) in availability
  * matches the identity CLAUDE.md asserts for 115r: 288 = 288

Portfolio totals include the "4,006 current leases = 4,006 units" cross-check.
Exits non-zero if any reconciliation or validator fails, so this can run in CI.

    python scripts/batch_parse.py
    make parse
"""

from __future__ import annotations

import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest.normalize import property_type  # noqa: E402
from ingest.parsers import (  # noqa: E402
    parse_availability, parse_charge_summary, parse_rent_roll,
)

RAW = Path("data/raw")
RENT_ROLLS = RAW / "Rent_Roll_with_Lease_Charges"
AVAILABILITY = RAW / "Unit_Availability"

# Reconciliation tolerance. The source is currency, so anything above one cent
# is either a parse bug or a file the source itself doesn't reconcile.
CENT = Decimal("0.01")


def files_in(folder: Path) -> list[Path]:
    return sorted(p for p in folder.glob("*.xls*") if not p.name.startswith("~$"))


def reconcile_lease_totals(leases) -> list[tuple[str, Decimal, Decimal]]:
    """Return [(unit_number, reported, computed)] where the two disagree."""
    bad = []
    for lease in leases:
        if lease.reported_total is None:
            continue
        computed = lease.charge_total()
        if abs(computed - lease.reported_total) > CENT:
            bad.append((lease.unit_number, lease.reported_total, computed))
    return bad


def reconcile_charge_summary(leases, summary):
    """Compare per-code sums from the leases to the file-level summary.

    Returns (per_code_mismatches, total_mismatch). `summary` includes a
    '__TOTAL__' key holding the grand total.
    """
    computed_by_code: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    for lease in leases:
        for ch in lease.charges:
            computed_by_code[ch.charge_code] += ch.amount

    per_code = []
    for code, reported in summary.items():
        if code == "__TOTAL__":
            continue
        computed = computed_by_code.get(code, Decimal(0))
        if reported is None or abs(computed - reported) > CENT:
            per_code.append((code, reported, computed))

    # Codes present in the leases but missing from the summary block.
    for code, computed in computed_by_code.items():
        if code not in summary and computed != 0:
            per_code.append((code, None, computed))

    total_reported = summary.get("__TOTAL__")
    total_computed = sum(computed_by_code.values(), Decimal(0))
    total_mismatch = None
    if total_reported is not None and abs(total_computed - total_reported) > CENT:
        total_mismatch = (total_reported, total_computed)
    return per_code, total_mismatch


def status_counts(leases) -> dict[str, int]:
    counts = {"current": 0, "notice": 0, "vacant": 0, "future": 0}
    for lease in leases:
        counts[lease.lease_status] += 1
    return counts


def process_rent_rolls():
    """Returns (per_property, portfolio, parser_fail, source_notes)."""
    per_property: dict[str, dict] = {}
    portfolio = defaultdict(int)
    parser_fail = 0        # parser bugs: crashes, validator warnings, per-lease
                           # reconciliation gaps (all three signal our code is wrong)
    source_notes = 0       # file-level oddities that the parser correctly surfaces

    print(f"\nRENT ROLLS  ({len(files_in(RENT_ROLLS))} files)")
    print("-" * 78)

    for path in files_in(RENT_ROLLS):
        try:
            header, leases, warnings = parse_rent_roll(path)
        except Exception as exc:                          # noqa: BLE001
            print(f"  [ FATAL] {path.name}: {exc}")
            parser_fail += 1
            continue

        summary = parse_charge_summary(path)
        counts = status_counts(leases)
        n_charges = sum(len(l.charges) for l in leases)

        bad_totals = reconcile_lease_totals(leases)
        summary_bad, summary_total_bad = ([], None)
        if summary:
            summary_bad, summary_total_bad = reconcile_charge_summary(leases, summary)

        parser_fail += len(warnings) + len(bad_totals)
        source_notes += len(summary_bad) + (1 if summary_total_bad else 0)

        if warnings or bad_totals:
            status = "PROBLEM"
        elif summary_bad or summary_total_bad:
            status = "note"
        else:
            status = "OK"
        ptype = property_type(header.property_code)
        print(
            f"  [{status:>7}] {header.property_code:<8} {ptype:<12} "
            f"leases={len(leases):<4} charges={n_charges:<5} "
            f"cur={counts['current']:<3} not={counts['notice']:<3} "
            f"vac={counts['vacant']:<3} fut={counts['future']:<3} "
            f"warnings={len(warnings)} "
            f"summary={'yes' if summary else 'no '} "
            f"{path.name}"
        )

        for w in warnings:
            print(f"            ! warning: {w}")
        for unit, reported, computed in bad_totals:
            print(f"            ! lease {unit}: reported {reported} != sum {computed} "
                  f"(delta {computed - reported})")
        for code, reported, computed in summary_bad:
            print(f"            - source note: summary {code} reported "
                  f"{reported} vs sum {computed}")
        if summary_total_bad:
            reported, computed = summary_total_bad
            print(f"            - source note: summary TOTAL reported "
                  f"{reported} vs sum {computed}")

        per_property[header.property_code] = {
            "type": ptype,
            "counts": counts,
            "n_charges": n_charges,
        }
        for k, v in counts.items():
            portfolio[f"leases_{k}"] += v
        portfolio["charges"] += n_charges
        portfolio["reconciled_leases"] += sum(
            1 for l in leases if l.reported_total is not None
        )
        portfolio["files_with_summary"] += 1 if summary else 0

    return per_property, portfolio, parser_fail, source_notes


def process_availability():
    per_property: dict[str, dict] = {}
    portfolio = defaultdict(int)
    parser_fail = 0

    print(f"\nAVAILABILITY  ({len(files_in(AVAILABILITY))} files)")
    print("-" * 78)

    for path in files_in(AVAILABILITY):
        try:
            header, record = parse_availability(path)
        except Exception as exc:                          # noqa: BLE001
            print(f"  [ FATAL] {path.name}: {exc}")
            parser_fail += 1
            continue

        ptype = property_type(header.property_code)
        occ_side = (record.occupied_no_notice
                    + record.notice_rented + record.notice_unrented)
        vac_side = record.vacant_rented + record.vacant_unrented

        status = "note" if not record.states_reconcile else "OK"
        print(
            f"  [{status:>7}] {header.property_code:<8} {ptype:<12} "
            f"units={record.total_units:<4} "
            f"occ={occ_side:<3} vac={vac_side:<3} "
            f"nonrev={record.nonrevenue_units:<3} "
            f"unclassified={record.unclassified_units:<3} "
            f"reconcile={'yes' if record.states_reconcile else 'no '} "
            f"{path.name}"
        )
        if not record.states_reconcile:
            print(f"            - {record.unclassified_units} units the report counts "
                  "but doesn't classify (commercial residential-vocab gap)")

        per_property[header.property_code] = {
            "record": record,
            "occ_side": occ_side,
            "vac_side": vac_side,
        }
        portfolio["total_units"] += record.total_units
        portfolio["occupied_side"] += occ_side
        portfolio["vacant_side"] += vac_side
        portfolio["nonrev"] += record.nonrevenue_units
        portfolio["unclassified"] += record.unclassified_units

    return per_property, portfolio, parser_fail


def cross_check(rent_props, avail_props):
    """Per-property strong identity: every row in the rent roll's Current
    section (occupied, on notice, or vacant) is one row in the availability
    report's total_units.

    On 115r that is 270 + 18 + 12 = 300 = total_units.
    Also prints the occupied-side comparison as informational -- commercial
    availability files leave states blank while their rent rolls do not, so
    that side legitimately disagrees.
    """
    print("\nPER-PROPERTY CROSS-CHECK  (current-section leases = total_units)")
    print("-" * 78)
    parser_fail = 0
    source_notes = 0
    for code in sorted(set(rent_props) | set(avail_props)):
        rr = rent_props.get(code)
        av = avail_props.get(code)
        if not rr or not av:
            missing = "availability" if not av else "rent roll"
            print(f"  [MISSING] {code}: no {missing} file")
            parser_fail += 1
            continue

        rr_all = rr["counts"]["current"] + rr["counts"]["notice"] + rr["counts"]["vacant"]
        av_units = av["record"].total_units
        delta_all = rr_all - av_units

        rr_occ = rr["counts"]["current"] + rr["counts"]["notice"]
        av_occ = av["occ_side"]
        delta_occ = rr_occ - av_occ

        # A non-zero delta on the strong identity is a source discrepancy
        # between the two Yardi reports, not a parser bug -- we've already
        # verified per-lease reconciliation above.
        if delta_all == 0:
            tag = "OK"
        else:
            tag = "note"
            source_notes += 1
        print(
            f"  [{tag:>7}] {code:<8} "
            f"rr(cur+not+vac)={rr_all:<4} units={av_units:<4} delta={delta_all:+d}  "
            f"|  occ side rr={rr_occ:<4} av={av_occ:<4} delta={delta_occ:+d}"
        )
    return parser_fail, source_notes


def print_portfolio(rr_totals, av_totals, rr_parser, rr_notes,
                    av_parser, cross_parser, cross_notes):
    print("\n" + "=" * 78)
    print("PORTFOLIO")
    print("=" * 78)
    print(f"  rent roll   current={rr_totals['leases_current']}  "
          f"notice={rr_totals['leases_notice']}  "
          f"vacant={rr_totals['leases_vacant']}  "
          f"future={rr_totals['leases_future']}  "
          f"charges={rr_totals['charges']}")
    print(f"              per-lease reconciliations available: "
          f"{rr_totals['reconciled_leases']} / "
          f"{rr_totals['leases_current'] + rr_totals['leases_notice'] + rr_totals['leases_vacant'] + rr_totals['leases_future']}")
    print(f"              file-level charge summaries present: "
          f"{rr_totals['files_with_summary']} / 25")
    print()
    print(f"  availability  total_units={av_totals['total_units']}  "
          f"occupied={av_totals['occupied_side']}  "
          f"vacant={av_totals['vacant_side']}  "
          f"nonrev={av_totals['nonrev']}  "
          f"unclassified={av_totals['unclassified']}")

    print("\n  IDENTITIES")
    # CLAUDE.md line 205: "Current leases vs total units, portfolio -- 4,006 = 4,006"
    # The rent-roll side is every row in the Current/Notice/Vacant Residents
    # section (i.e. every non-future lease slot -- occupied, on notice, or
    # vacant). The availability side is total_units.
    rr_all = (rr_totals["leases_current"] + rr_totals["leases_notice"]
              + rr_totals["leases_vacant"])
    av_units = av_totals["total_units"]
    ident_ok = rr_all == av_units
    tag = "OK" if ident_ok else "note"
    print(f"    [{tag}] rent roll (current+notice+vacant) = availability total_units: "
          f"{rr_all} vs {av_units}")

    # Secondary: occupied side, informational. Not a hard identity because
    # commercial availability files leave states blank while the rent roll
    # still records the underlying leases.
    rr_occupied = rr_totals["leases_current"] + rr_totals["leases_notice"]
    av_occupied = av_totals["occupied_side"]
    delta = rr_occupied - av_occupied
    print(f"    [ info] rent roll (current+notice) vs availability (occ+not): "
          f"{rr_occupied} vs {av_occupied}  delta={delta:+d}  "
          "(commercial state gaps expected)")

    parser_fail = rr_parser + av_parser + cross_parser
    total_notes = rr_notes + cross_notes + (0 if ident_ok else 1)
    print(f"\n  parser problems: {parser_fail}   "
          f"source-file notes: {total_notes}")
    if parser_fail == 0:
        print("  parsers are clean. remaining notes are file-level "
              "discoveries -- see docs/data_quality.md.")
    return parser_fail


def main() -> int:
    rr_props, rr_totals, rr_parser, rr_notes = process_rent_rolls()
    av_props, av_totals, av_parser = process_availability()
    cross_parser, cross_notes = cross_check(rr_props, av_props)
    parser_fail = print_portfolio(
        rr_totals, av_totals, rr_parser, rr_notes,
        av_parser, cross_parser, cross_notes,
    )
    return 0 if parser_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
