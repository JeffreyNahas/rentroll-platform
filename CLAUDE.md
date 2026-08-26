# CLAUDE.md

Orientation for anyone (human or agent) working in this repo. Read this
first. It stays short on purpose — everything deep lives in the docs listed
at the bottom.

---

## What this is

A take-home case study for an **AI & Software Engineering internship at
Aker** — a vertically integrated real-estate firm running an internal AI
platform over Yardi Voyager data.

Inputs: 25 × `Rent Roll with Lease Charges` + 25 × `Unit Availability`
Excel exports, all as of 02/25/2026. Deliverable: private GitHub repo +
live walkthrough. Pitch and demo one-liner: `docs/walkthrough.md`.

---

## Non-negotiables

- **Never commit the source data.** `data/` is gitignored. Test fixtures
  must be synthetic — the rent rolls contain resident names, balances,
  and move-in dates.
- **Never commit `.env`.** `.env.example` only, with placeholder values.
- **Never backdate commits.** Timestamps are visible in review.
- Conventional Commits: `feat(scope):`, `fix:`, `test:`, `docs:`, `chore:`.
- Don't merge a red build.

---

## Load-bearing facts

Facts that shape every design decision. Full write-up in
`docs/data_quality.md`; parser-facing details in `ingest/parsers/`.

- **Mixed-use portfolio.** 25 properties across residential / affordable /
  commercial / land / management. Property code suffix encodes type
  (`115r`, `126a`, `134c`, `134land`, `altapm`).
- **Commercial has no `RENT` code.** Base rent is `RENTRETL` (retail) or
  `RNTPROF` (professional). A query filtering `WHERE charge_code = 'RENT'`
  silently zeroes five properties. **Always resolve base rent through
  `charge_code.category`.** Unmapped codes must be load-time errors, never
  a silent `other`.
- **Availability report is property-level.** 25 files = 25 data rows.
  Loaded as an independent *control total*, not a parallel unit-grained
  source.
- **Future applicants are excluded from occupancy.** 93 portfolio-wide,
  signed but not moved in. `lease.section = 'future'` marks them.
- **Snapshot grain.** Every fact hangs off `report_snapshot`. Reloads are
  idempotent via SHA-256 file hash.
- **Two-tier reconciliation.** Per-lease `Total` rows (4,106 across 25/25
  files) are primary. File-level charge summary is secondary (16/25 files).
- **Known source-file oddities:** 153c rent roll leaves `unit_type` blank
  (parser handles it); 153c availability reports 0 units for a property
  with 7 leases; 462a summary block internally off by $1,310 in
  `SUBSIDY`/`SEC8CRD`. All three surface as `ingest_audit` failures.

---

## Design rules

Applies to anything added from here on.

1. **Never let the LLM compute a number.** Tools return structured JSON
   from SQL; the model narrates. A post-response numeric grounding check
   verifies every figure in a response appeared in tool output, retries
   once, then fails closed with *"I can't verify that figure from the
   data."*
2. **No raw text-to-SQL.** Build a curated read-only toolbelt with a
   guarded `run_readonly_sql` escape hatch (sqlglot AST, SELECT-only, row
   cap, `rri_readonly` role, 5s timeout).
3. **Every metric carries its source.** Especially occupancy — it comes
   from the availability report where `states_reconcile`, from the rent
   roll where it doesn't. Surface `occupancy_source` on every row.
4. **Never blend metrics across property types.** Averaging a 3-unit
   retail strip with a 775-unit apartment complex produces a meaningless
   number.
5. **Base rent resolves through `charge_code.category`**, never a literal
   code match.
6. **Surface data problems, don't hide them.** `unclassified_units`,
   `ingest_error`, and `ingest_audit` exist to be displayed. The dashboard
   should have a data-quality panel.
7. **Reconciliation is two-tier.** Per-lease totals are primary — a
   failure localizes to one lease. The file-level charge summary is a
   secondary cross-check on the 16 files that have it.
8. **PII.** Store `display_name` but gate output behind `MASK_PII`. With
   it on, the API and agent return `Resident #4821`. Demo it on.

---

## Where to look next

| Doc | When to read |
|---|---|
| `STATUS.md` | Start of every work session — what shipped, DB row counts, next step |
| `TODO.md` | Planning the next task |
| `docs/journal.md` | Understanding *why* a past decision was made, or what mistake it fixed |
| `docs/architecture.md` | Designing new tables, views, or services |
| `docs/data_quality.md` | Working on parsers, investigating a reconciliation failure |
| `docs/walkthrough.md` | Prepping for the interview |

Working notes on decisions and mistakes go in `docs/journal.md` at the end
of a work session — one short entry per session. That file is the audit
trail; `git log` isn't enough on its own.

---

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # devpass is fine, throwaway container
make up                       # postgres on :5432, adminer on :8080
make migrate
make discover                 # profile source files
make parse                    # parser + reconciliation batch
make load                     # ingest into the DB (idempotent)
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

Adminer at `localhost:8080` — server `db` (resolves inside the Docker
network, not `localhost`), user `postgres`, database `rentroll`.

**Makefile note:** recipe lines need literal tabs. Editors that expand tabs
to spaces will break it.
