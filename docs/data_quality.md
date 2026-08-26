# Data Quality Report

Findings from profiling all 50 source files before writing any parser, and the
design decisions each finding forced.

Produced by `scripts/discover.py`. The script writes nothing to the database —
it verifies that every file matches the structure observed by hand in one file
per family, and reports deviations.

**Inputs:** 25 × Rent Roll with Lease Charges, 25 × Unit Availability
**Snapshot date:** all files as of 02/25/2026

---

## Summary

| | |
|---|---|
| Files profiled | 50 |
| Layout variants | 1 per family |
| Properties | 25 |
| Current leases | 4,006 |
| Future applicants | 93 |
| Vacant units | 170 |
| Total units | 4,006 |
| Non-revenue units | 13 |
| Distinct charge codes | 32 |
| Blocking problems | 3 (all explained below) |

---

## 1. File structure

Both report families use a **two-row header**. Long column headings wrap across
two rows — row 3 holds `Occupied` while row 4 holds `No Notice`, which together
form one column. Reading either row alone shifts every subsequent field.

| | Rent Roll | Unit Availability |
|---|---|---|
| Title block | rows 0–3 | rows 0–2 |
| Header rows | 4 + 5 | 3 + 4 |
| Data starts | row 7 | row 5 |
| Columns | 14 | 18 |
| Grain | one row per lease, plus indented charge rows | **one row per property** |

**Decision:** header labels are declared as constants and asserted per file
rather than inferred, so a layout change fails loudly instead of loading
silently-wrong data.

### Rent roll row structure

Each lease block is:

```
A103 | 115mxA05 | 755 | t0019683 | Resident 1 | 2472 | RENT | 2480 | ...   ← lease + first charge
     |          |     |          |            |      | PETFEEM | 50        ← charge sub-row
     |          |     |          |            |      | AMENITY | 40
     |          |     |          |            |      | Total   | 2760      ← block total
                                                                            ← blank separator
```

Two non-obvious properties:

- **The first charge sits on the lease row itself**, not below it. A parser that
  only collects sub-rows silently drops one charge per lease — usually the
  largest one.
- **Charge order is not fixed.** Some leases lead with `PARKING` and place
  `RENT` third, so column 6 cannot be assumed to be base rent.

Rent rolls have up to two sections: `Current/Notice/Vacant Residents` and
`Future Residents/Applicants`. Properties with no pending applications omit the
second entirely.

**Decisions:**
- The parser is a stateful row classifier, not a `read_excel` call.
- Charges are collected from both the lease row and its sub-rows.
- `lease_charge` has **no unique constraint** on `(lease_id, charge_code)` —
  leases legitimately carry the same code twice (two parking spaces, two pet
  fees).
- `lease.section` distinguishes current from future. Future applicants are
  signed but not moved in; including them would inflate occupancy.

### Unit Availability is property-level, not unit-level

Each file contains a single data row summarising the whole property:

```
115r | Canfield Park | Avg Sq Ft 869 | Avg Rent 2546 | Units 300
Occupied No Notice 270 | Vacant Rented 5 | Vacant Unrented 7
Notice Rented 4 | Notice Unrented 14 | Avail 21 | Model 0 | Down 0 | Admin 0
% Occ 96 | % Occ w/NonRev 96 | % Leased 97.67 | % Trend 93
```

**Decision:** the rent roll is the unit-grained fact table; availability is an
independent property-level **control total** used to validate it. Modelling
availability per-unit would have meant inventing rows that do not exist.

---

## 2. The portfolio is mixed-use

The property code suffix encodes the asset type, and each type uses a different
rent structure.

| Type | Count | Codes |
|---|---|---|
| Residential | 12 | 115r, 126r, 134r, 138r, 139r, 144r, 153r, 175r, 176r, 183r, 184r, 185r |
| Affordable | 6 | 126a, 138a, 143a, 153a, 183a, 462a |
| Commercial | 5 | 134c, 139c, 143c, 153c, 183c |
| Land | 1 | 134land |
| Management entity | 1 | altapm |

### Charge codes by type

| Type | Codes |
|---|---|
| Residential (25) | AMENITY, BIKE, CONAMEN, CONEMP, CONGAR, CONPARK, CONPETM, CONRENT, CONSTOR, GARAGE, HOMEPCKG, MTM, PARKING, PETFEE, PETFEEM, **RENT**, RENTHAP, SALESTX, SDFEE, SEC8CRD, STORAGE, SUBSIDY, TRASH, W/D, WATER |
| Affordable (19) | AMENITY, BIKE, CONPARK, CONRENT, GARAGE, HOMEPCKG, MTM, PARKING, PETFEEM, **RENT, RENTAFF**, SALESTX, SDFEE, SEC8CRD, STORAGE, SUBSIDY, TRASH, W/D, WATER |
| Commercial (7) | AMENITY, CAMEST, CAMINSR, **RENTRETL, RNTPROF**, RETXEST, UTILCOM |
| Land / management | none — no leases |

**Only `AMENITY` appears in every type.**

### The most important consequence

**Commercial properties have no `RENT` charge code at all.** A query filtering
`WHERE charge_code = 'RENT'` returns zero rent for all five commercial
properties. Base rent has to be defined per property type:

| Type | Base rent codes |
|---|---|
| Residential | `RENT`, `RENTHAP` |
| Affordable | `RENT`, `RENTAFF` |
| Commercial | `RENTRETL`, `RNTPROF` |

Commercial files also carry `CAMEST`, `CAMINSR`, and `RETXEST` — common area
maintenance, insurance, and real estate tax **recoveries**. These are revenue
but not rent, and folding them into rent-per-square-foot would overstate it.

`RENTHAP`, `SEC8CRD`, and `SUBSIDY` appear under *residential*, not only
affordable — some market-rate properties carry subsidised units, so the
affordable split exists at the unit level too, not purely per property.

**Decisions:**
- `property.property_type` column, populated from the code suffix.
- `charge_code.category` seeded with all 32 codes, including a `recovery`
  category for commercial pass-throughs and `subsidy` for housing assistance.
- All rent metrics resolve base rent through the category map, never a literal
  code match.
- Portfolio metrics are **segmented by property type**, never blended. Averaging
  the occupancy of a 3-unit retail strip with a 775-unit apartment complex
  produces a meaningless number.

---

## 3. Cross-report validation

**Current leases (4,006) equals total units (4,006) across all 25 properties.**

These figures come from two independently generated reports, so the agreement is
strong evidence the rent roll parser reads lease rows correctly and excludes
charge rows, totals, and future applicants.

**Decision:** this becomes a post-load assertion in the loader, checked
per property rather than only in aggregate — a portfolio total can net out two
properties with offsetting errors.

---

## 4. Reconciliation strategy

Both reconciliation targets are parsed from the source files themselves.

| Check | Coverage | What it catches |
|---|---|---|
| **Per-lease `Total` rows** | 4,106 checks across **25/25 files** | Charge-level parse errors, localised to a single lease |
| **File-level charge summary** | **16/25 files** | Whole-file drift by charge code |

Six populated rent rolls omit the file-level `Summary of Charges by Charge Code`
block: **134c, 176r, 183a, 183r, 184r, 185r**. Three further files (134land,
183c, altapm) have no leases at all, so nothing to reconcile.

Validated on Canfield Park (115r), where both checks are available — all 10
charge codes and the file total matched to the cent:

```
  code        reported       parsed      delta
  AMENITY        12,020.00    12,020.00     0.00
  CONRENT        -8,936.39    -8,936.39     0.00
  PARKING        28,490.00    28,490.00     0.00
  RENT          754,322.32   754,322.32     0.00
  ...
  TOTAL         791,650.93   791,650.93     0.00
```

**Decision:** per-lease totals are the primary check because they cover every
file and localise failures. The file-level summary is a secondary cross-check
where present. Files without it are recorded as `file_summary: false` in the
audit table rather than being skipped or silently marked as passing.

---

## 5. Known data limitations

### Commercial occupancy states are incomplete

For every property, total units should equal the five occupancy states plus
non-revenue units (model, down, admin). Three commercial properties break this:

| Property | Units | States | Non-revenue | Unclassified |
|---|---|---|---|---|
| 134c | 3 | 0 | 0 | 3 |
| 139c | 10 | 0 | 0 | 10 |
| 143c | 29 | 25 | 0 | 4 |

For 134c and 139c, Yardi reports a unit count and classifies nothing. This is
not a header misalignment — that would move values, not zero them.

143c decodes consistently: Units 29, Occupied No Notice 13, Vacant Unrented 12,
and `% Occ` of 44.83% — which is exactly 13/29. So the report's own occupancy
figure agrees with 13 occupied, leaving 4 units in no state at all.

The occupancy state vocabulary (Occupied / Vacant / Notice) is a residential
concept. Commercial suites do not map onto it cleanly, so Yardi populates it
partially or not at all.

**Decisions:**
- `property_availability.unclassified_units` stores the gap explicitly. It is
  never redistributed across the states or hidden.
- `property_availability.states_reconcile` flags whether the identity holds.
- Occupancy views carry an `occupancy_source` column: `availability_report`
  where the states reconcile, `rent_roll_derived` where they do not.
- Every occupancy figure surfaced through the API or the agent reports which
  source produced it.

### Non-revenue units

13 units across the portfolio are model, down, or admin units — occupied by no
one and not rentable. This is why the source report carries both `% Occ` and
`% Occ w/NonRev`.

**Decision:** non-revenue units are excluded from the occupancy denominator,
and stored separately so either figure can be reproduced.

### Empty rent rolls

`134land`, `183c`, and `altapm` contain no lease rows (15, 15, and 46 rows
respectively — title, header, and totals only). This is expected: raw land and a
management entity have no units to lease.

**Decision:** empty files load a snapshot with zero leases rather than failing.
An empty result and a parse failure must not look the same.

---

## 6. Decisions summary

| Finding | Design decision |
|---|---|
| Two-row wrapped headers | Assert expected labels per file; fail loudly on drift |
| First charge on the lease row | Parser collects from lease row and sub-rows |
| Duplicate charge codes per lease | No unique constraint on `(lease_id, charge_code)` |
| Two sections, one often absent | `lease.section`; future applicants excluded from occupancy |
| Availability is property-level | Modelled as a control total, not a unit-grained table |
| Mixed-use portfolio | `property.property_type`; metrics segmented, never blended |
| No `RENT` code in commercial | Base rent resolved via `charge_code.category` |
| Commercial CAM/tax recoveries | Separate `recovery` category, excluded from rent metrics |
| 4,006 leases = 4,006 units | Per-property post-load assertion |
| 9 files lack the charge summary | Per-lease totals as primary reconciliation (25/25 files) |
| Commercial states incomplete | `unclassified_units` stored; `occupancy_source` on every metric |
| Empty rent rolls | Load a zero-lease snapshot; never conflate empty with failed |

---

## Reproducing

```bash
python scripts/discover.py
```

Exits after reporting; makes no database connection and writes no data.