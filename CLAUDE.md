# CLAUDE.md

Context for working on this codebase. Read this before making changes.

---

## What this is

A take-home case study for an **AI & Software Engineering internship at Aker**,
a vertically integrated real estate investment and operating firm. Aker owns,
develops, and operates residential and mixed-use properties, and runs an
internal AI platform on top of Yardi Voyager data.

**The brief, verbatim from the recruiter:**

1. Design a relational database schema to store as much data as you can extract
   from the Excel files.
2. Develop a Python script to process all the files and load the data into the
   database.
3. Build a presentation layer for the data — a dashboard, an LLM-powered
   chatbot, or anything else. Be creative and build whatever best showcases
   your skills.

**Inputs:** 25 × `Rent Roll with Lease Charges` + 25 × `Unit Availability`
Excel files (Yardi exports), all as of 02/25/2026.

**Deliverable:** a private GitHub repo, followed by a live walkthrough of the
code and a demo.

### The differentiation thesis

Aker's platform page states three engineering principles. Every design decision
in this repo maps to one of them, and that mapping is the pitch:

| Their principle | How this repo implements it |
|---|---|
| **Facts before fluency** | Every number is computed in SQL. The LLM never does arithmetic — it selects tools and narrates results. Enforced by a post-response numeric grounding check. |
| **Evidence before assertion** | Every fact row carries `source_row` and `snapshot_id`; every API and agent response carries citations back to file and row. |
| **Governance before action** | Read-only DB role, SQL AST validation, row caps, 5s statement timeout, full query audit log. |

Plus an **eval harness** — golden question set, tool-trajectory scoring, exact
numeric checks. The interviewer said their team is still figuring out evals, so
this is the highest-leverage thing in the submission.

**Demo one-liner:** *"I didn't build a dashboard with a chatbot bolted on. I
built a governed semantic layer over the rent roll and gave an agent read-only
tools on top of it — so every number traces to a row in a file you sent me, and
I can prove the agent's accuracy with a regression suite."*

---

## Non-negotiables

- **Never commit the source data.** The rent rolls contain resident names,
  balances, and move-in dates. `data/` is gitignored. Test fixtures must be
  synthetic.
- **Never commit `.env`.** `.env.example` only, with placeholder values.
- **Never backdate commits.** Timestamps are visible in review.
- Conventional Commits: `feat(scope):`, `fix:`, `test:`, `docs:`, `chore:`.
- Don't merge a red build.

---

## What the data actually looks like

All of this was established empirically by `scripts/discover.py`, not assumed.
Full write-up in `docs/data_quality.md`. The findings below are load-bearing —
several of them are non-obvious and easy to get wrong.

### Both families share a report shell

```
row 0    report title
row 1    Property Name (property_code)      e.g. "Canfield Park (115r)"
row 2    As Of = MM/DD/YYYY
row 3    Month Year = MM/YYYY               (rent roll only)
row 4-5  two-row header                     (rows 3-4 for availability)
```

**Headers wrap across two rows.** In the availability report, row 3 holds
`Occupied` and row 4 holds `No Notice` — one column, `Occupied No Notice`.
Reading either row alone shifts every field after it. Both rows must be joined.

### Rent roll: a sequence of lease blocks, not a table

```
A103 | 115mxA05 | 755 | t0019683 | Resident 1 | 2472 | RENT | 2480 | ...  <- lease + FIRST charge
     |          |     |          |            |      | PETFEEM | 50        <- charge sub-row
     |          |     |          |            |      | AMENITY | 40
     |          |     |          |            |      | Total   | 2760      <- block total
                                                                            <- blank separator
```

Three properties that break naive parsers:

1. **The lease's first charge sits on the lease row itself** (columns 6–7).
   Collecting only sub-rows silently drops one charge per lease.
2. **Charge order is not fixed.** Some leases lead with `PARKING` and place
   `RENT` third. Column 6 is not "base rent".
3. **Charge codes repeat within a lease** (two parking spaces, two pet fees).
   Hence no unique constraint on `(lease_id, charge_code)`.

Two sections: `Current/Notice/Vacant Residents` and
`Future Residents/Applicants`. Future applicants are signed but not moved in —
93 portfolio-wide — and must be excluded from occupancy. Properties with no
pending applications omit the section entirely.

Vacant units show `VACANT` in the resident and name columns.
Notice status is **derived**: `move_out_date` populated on a current lease.

Column positions (constants in `ingest/parsers/rent_roll.py`):

```
0 unit          1 unit_type    2 sqft         3 resident      4 name
5 market_rent   6 charge_code  7 amount       8 resident_dep  9 other_dep
10 move_in      11 lease_exp   12 move_out    13 balance
```

### Unit Availability is property-level, not unit-level

**One data row per file.** 25 files = 25 rows, not 25 × N units. This is the
single most important structural fact — it is not a parallel unit-grained
source. It is loaded as an independent **control total** for validating the
rent roll.

Column positions (joined header, data on row 5):

```
0 property_code  1 name  2 avg_sqft  3 avg_rent  4 units
5 occupied_no_notice  6 vacant_rented  7 vacant_unrented
8 notice_rented  9 notice_unrented  10 available
11 model  12 down  13 admin
14 pct_occ  15 pct_occ_nonrev  16 pct_leased  17 pct_trend
```

The occupancy identity:

```
units = (occupied_no_notice + vacant_rented + vacant_unrented
         + notice_rented + notice_unrented) + model + down + admin
```

This is the best available check that the two-row header was joined correctly.

### The portfolio is mixed-use

The property code suffix encodes asset type. This was **not stated in the
brief** — it was inferred from the charge-code vocabulary.

| Type | Count | Codes |
|---|---|---|
| Residential | 12 | 115r, 126r, 134r, 138r, 139r, 144r, 153r, 175r, 176r, 183r, 184r, 185r |
| Affordable | 6 | 126a, 138a, 143a, 153a, 183a, 462a |
| Commercial | 5 | 134c, 139c, 143c, 153c, 183c |
| Land | 1 | 134land |
| Management entity | 1 | altapm |

**32 charge codes. Only `AMENITY` appears in every property type.**

The critical consequence: **commercial properties have no `RENT` code at all.**
Their base rent is `RENTRETL` (retail) and `RNTPROF` (professional suites). Any
query filtering `WHERE charge_code = 'RENT'` silently returns zero rent for five
properties. Base rent must always resolve through `charge_code.category`.

Commercial also carries `CAMEST`, `CAMINSR`, `RETXEST` — CAM, insurance, and
real estate tax **recoveries**. Revenue, but not rent; excluded from
rent-per-square-foot.

`RENTHAP`, `SEC8CRD`, `SUBSIDY` appear under *residential*, not only affordable
— some market-rate properties carry subsidized units, so the split is at the
unit level too.

### Known data limitations

**Commercial occupancy states are incomplete.** Three properties report a unit
count that the states don't account for:

| Property | Units | States | Unclassified |
|---|---|---|---|
| 134c | 3 | 0 | 3 |
| 139c | 10 | 0 | 10 |
| 143c | 29 | 25 | 4 |

Not a parse bug — a misaligned header would move values, not zero them. The
Occupied/Vacant/Notice vocabulary is a residential concept and Yardi does not
apply it consistently to commercial suites. `143c` reports `% Occ` 44.83% which
is exactly 13/29, so the source agrees with its own partial classification.

**Handling:** store the gap as `unclassified_units`, flag `states_reconcile`,
and select occupancy source per property. Never redistribute or hide it.

**Empty rent rolls.** `134land`, `183c`, `altapm` have no leases (15, 15, 46
rows — title, header, totals only). These load a snapshot with zero leases
rather than failing. `source_file.n_rows` distinguishes empty from failed.

**Nine files lack the file-level charge summary.** Six of them are populated:
`134c`, `176r`, `183a`, `183r`, `184r`, `185r`. Hence the two-tier
reconciliation below.

### Validation results

| Check | Result |
|---|---|
| Current leases vs total units, portfolio | **4,006 = 4,006** (two independent reports) |
| Per-lease totals, Canfield Park | 309/309 present, 0 mismatches |
| Charge-code summary, Canfield Park | 10/10 codes + total, exact to the cent |
| Occupied cross-check, Canfield Park | 288 (rent roll) = 288 (availability) |
| Status derivation, Canfield Park | 270 current / 18 notice = availability's 270 / (4+14) |

---

## Architecture

```
Excel files
    |
    v  scripts/discover.py        structure validation, no DB writes
    v  ingest/parsers/            stateful row classifiers -> pydantic records
    v  ingest/loader.py           idempotent load + reconciliation
    |
Postgres    bronze (raw_row) -> silver (typed entities) -> gold (views)
    |
    v  api/                       FastAPI, every response carries citations
    v  web/  or  agent/           dashboard and/or governed tool-calling agent
    v  evals/                     golden set, trajectory + numeric scoring
```

### Schema design decisions

**Snapshot grain.** The files are point-in-time reports, not master data. Every
fact row references a `report_snapshot`. This makes reloads idempotent, allows
a future month of files to land alongside this one, and is the honest answer to
*"what if we hand you next month's 50 files?"*

**`lease` is snapshot-grained, not SCD2.** The exports carry no lease
identifier. Threading a lease across snapshots would require fuzzy matching on
(unit, resident, move-in) that cannot be validated. With the Yardi API instead
of exports, true SCD2 would be right.

**`lease.reported_total`** stores the block's own Total row, so reconciliation
is a SQL query over loaded data rather than a transient check during parsing.

**Bronze layer.** `raw_row` keeps every source row as JSONB so any parse can be
replayed without re-reading spreadsheets.

### Tables

```
DIMENSIONS   property (property_type)  unit_type  unit  resident
             charge_code (category)
PROVENANCE   source_file (file_hash, n_rows)  report_snapshot  raw_row
FACTS        lease (section, lease_status, reported_total)
             lease_charge (no unique constraint on code)
             property_availability (unclassified_units, states_reconcile)
AUDIT        ingest_error  ingest_audit  query_audit  schema_migration
```

`charge_code.category` ∈ `base_rent | subsidy | concession | amenity | utility |
fee | recovery`. All 32 codes are seeded in migration 002. **An unmapped code
must be a load-time error, not a silent `other`.**

---

## Current state

### Done

| Component | Status |
|---|---|
| `scripts/discover.py` | Validates all 50 files. 3 problems (the commercial availability files), 16 notes, all explained in `docs/data_quality.md`. |
| `docs/data_quality.md` | Complete write-up of findings and the decisions they forced. |
| `docker-compose.yml` | Postgres 16 + Adminer, healthchecked. |
| `Makefile` | `up down reset migrate load discover eval test lint` |
| `db/migrations/001_*` | Full schema DDL. Applied and verified. |
| `db/migrations/002_*` | 32 charge codes with categories. Applied. |
| `db/migrations/003_*` | `rri_readonly` role, SELECT-only, 5s timeout. Applied. |
| `ingest/migrate.py` | Migration runner, tracks applied files in `schema_migration`. |
| `ingest/normalize.py` | `to_money` (parenthesized negatives), `to_date` (Excel serials), `property_type`. |
| `ingest/models.py` | Pydantic records with date-order and vacancy validators. |
| `ingest/parsers/` | Both parsers. **Validated against 115r: 309 leases, 1,320 charges, 0 warnings, all reconciliations exact.** |

Parsers return `(header, records, warnings)` and never raise on a single bad
row — a malformed row becomes a warning, not a crash that loses 308 good leases.

### Not done

1. **Batch parser test across all 25 rent rolls** — do this before the loader.
   Print per-file lease counts, warnings, and per-lease mismatch counts. You
   want to know now if a property trips a validator.
2. **`ingest/loader.py`** — file hashing for idempotency, upserts for
   property/unit/resident, one transaction per file, writes to `ingest_error`
   and `ingest_audit`.
3. **`ingest/cli.py`** — typer entrypoint behind `make load`.
4. **Gold views** — occupancy (segmented by property type, non-revenue units
   excluded from the denominator, `occupancy_source` carried through),
   loss-to-lease, expiration schedule, delinquency, charge mix.
5. **FastAPI** — metrics endpoints, every response with a `sources` block.
6. **Presentation layer** — Next.js + TS dashboard preferred (hits the JD stack
   and patches a stated gap); Streamlit is the time-boxed fallback.
7. **Agent** — curated read-only toolbelt, SQL AST guard, citations, numeric
   grounding check.
8. **Evals** — golden set, trajectory + numeric scoring, `evals/report.md`.
9. **Tests** — synthetic fixtures, parser unit tests.
10. **README** — quickstart, ERD, data quality summary, eval results.

### Immediate next step

Batch-test the parsers across all 25 rent rolls, then write `ingest/loader.py`.

---

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # devpass is fine, it's a throwaway container
make up                       # postgres on :5432, adminer on :8080
make migrate
make discover                 # validate the source files
make load                     # not yet implemented
```

Source files live in:

```
data/raw/Rent_Roll_with_Lease_Charges/    25 files   (gitignored)
data/raw/Unit_Availability/               25 files   (gitignored)
```

Inspect the database:

```bash
docker compose exec db psql -U postgres -d rentroll -c "\dt"
```

Adminer at `localhost:8080` — server `db` (not localhost; it resolves inside
the Docker network), user `postgres`, database `rentroll`.

**Makefile note:** recipe lines need literal tabs. Editors that expand tabs to
spaces will break it.

---

## Design rules for anything added from here

1. **Never let the LLM compute a number.** Tools return structured JSON from
   SQL; the model narrates. The numeric grounding check verifies every figure
   in a response appeared in tool output, retries once, then fails closed with
   *"I can't verify that figure from the data."*
2. **No raw text-to-SQL.** Build a curated read-only toolbelt with a guarded
   `run_readonly_sql` escape hatch (sqlglot AST validation, SELECT-only, row
   cap, `rri_readonly` role, statement timeout). Typed tools are a testable
   contract; unbounded text-to-SQL is not.
3. **Every metric carries its source.** Especially occupancy, which comes from
   the availability report where states reconcile and from the rent roll where
   they don't.
4. **Never blend metrics across property types.** Averaging a 3-unit retail
   strip with a 775-unit apartment complex produces a meaningless number.
5. **Base rent resolves through `charge_code.category`**, never a literal code
   match.
6. **Surface data problems, don't hide them.** `unclassified_units`,
   `ingest_error`, and `ingest_audit` exist to be displayed. The dashboard
   should have a data-quality panel.
7. **Reconciliation is two-tier.** Per-lease totals are primary — 4,106 checks
   across 25/25 files, and a failure localizes to one lease. The file-level
   charge summary is a secondary cross-check on the 16 files that have it.
8. **PII.** Store `display_name` but gate output behind `MASK_PII`. With it on,
   the API and agent return `Resident #4821`. Demo it on.

---

## Version control

Five branches, five PRs, squash-merged so `main` reads as one commit per stage:

| Branch | Contents |
|---|---|
| `feat/schema-and-infra` | docker-compose, Makefile, migrations, DDL ✅ merged |
| `feat/ingestion` | parsers, models, loader, reconciliation ← current |
| `feat/api-and-dashboard` | gold views, FastAPI, frontend |
| `feat/agent` | toolbelt, SQL guard, citations, grounding check |
| `feat/evals` | golden set, scoring, report |

PR descriptions carry the *why* and the trade-offs — they're artifacts to open
during the walkthrough, not bookkeeping. Tag the submitted state
`v1.0-submission`.

---

## Cut list, if time runs short

In order: Next.js → Streamlit · drop the `run_readonly_sql` escape hatch · drop
CI · drop PII masking · eval set 25 → 8 questions.

**Never cut:** reconciliation, provenance columns, the README data-quality
section, or a minimal eval set. Those are the differentiators; everything else
is table stakes.

---

## Walkthrough talking points

1. 50 files profiled before any parser was written — the portfolio turned out
   to be mixed-use with three different rent structures.
2. Only `AMENITY` is shared across all property types; commercial has no `RENT`
   code. A naive query would have silently zeroed five properties.
3. Snapshot grain, and re-running `make load` is a no-op via file hash.
4. The nested charge-row parser — hardest part of the format.
5. Two-tier reconciliation: 4,106 per-lease checks across 25/25 files.
6. 4,006 current leases = 4,006 units, from two independently generated
   reports.
7. Ask the agent something that trips the numeric grounding guard; let it fail
   closed.
8. Open `evals/report.md`: *"this is how I'd know if a prompt change made it
   worse."*

**Close with:** *"The constraint I set myself was that the LLM never produces a
number — it routes to SQL and narrates. That's why every figure on screen
traces to a row in a file you sent me."*