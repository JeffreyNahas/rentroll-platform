# Journal

Reverse-chronological session log. Each entry captures *why* a decision was
made and any mistake worth remembering. Facts about the *what* live in the
code; this file exists for the parts a `git log` doesn't tell you.

**Discipline:** one short entry per work session. Include mistakes and how
they were caught — silently fixing them loses the interview asset.

---

## 2026-08-26 — Gold views

Wrote `db/migrations/004_gold_views.sql` — nine plain views forming the
semantic layer above silver.

**Decisions**
- **Plain views, not materialized.** 4,106 leases / 9,177 charges is fast
  enough. Promote individual views only if a real API call shows latency.
- **`v_latest_snapshot` as a foundation view** rather than repeating the
  "latest per property per report_type" logic in every downstream view.
  One place to change when we eventually add time-travel.
- **`v_lease_detail` filters to `section = 'current'`.** Downstream views
  inherit the filter — future applicants are excluded from occupancy,
  loss-to-lease, delinquency, expirations, and portfolio KPIs by default.
  If we later need future-applicant metrics, they get a separate view.
- **Denominator source matches numerator source in occupancy.** When we
  fall back to `rent_roll_derived` for 153c, `rentable_units` also comes
  from the rent roll (`rr_occupied + rr_notice + rr_vacant = 7`), not from
  availability's `total_units - non_revenue - unclassified` which would be
  0 and force a NULL. Mixing sources is what silently produces nonsense
  percentages.
- **Portfolio ratios use `SUM(rentable_units)` from
  `v_occupancy_by_property`, not from `property_availability` directly.**
  This preserves each property's source-consistent denominator through the
  aggregation. Side effect: commercial `total_rentable_units` (49) exceeds
  commercial `total_units` (42) by 7 — that's the 153c anomaly propagating
  honestly rather than being hidden.
- **`v_data_quality_summary` is long-form `metric_name / value` (text).**
  The panel is going to grow; a rigid column schema would need re-migrating
  every time we add a metric. Text values are ugly but flexible; the
  frontend casts per row.
- **Charge mix uses `ABS()` in the pct denominator** so concessions (stored
  negative) don't reduce the visible gross revenue share.
- **Explicit `GRANT SELECT … TO rri_readonly` per view**, one line each.
  Migration 003 set default privileges, but being explicit here makes the
  security surface auditable in one place.

**Verified against known numbers**
- 115r: 288 occupied of 300 rentable, source `availability_report`;
  `base_rent_actual = $754,322.32` to the cent (matches
  `docs/data_quality.md` line 191).
- 153c: source `rent_roll_derived`, 1 occupied of 7 rentable.
- Portfolio: 12 residential / 6 affordable / 5 commercial / 1 land / 1 other.
- Data-quality view surfaces exactly 3 audit failures (matches the DB).

**Noteworthy observation (not a bug)**
- 115r `loss_to_lease` is **negative** (−$22,830, −3.12%): actual rent
  exceeds Market Rent. The SQL is correct — this reflects that Yardi's
  "Market Rent" field on this property is behaving as a floor value rather
  than an asking rent. Left visible in the view; if a business user reads
  it as "we're overcharging" they'll ask, which is the right conversation
  to have.

**Follow-ups**
- If the FastAPI layer proves any view slow, promote just that one to
  `MATERIALIZED VIEW` and add a `REFRESH MATERIALIZED VIEW` step to the
  end of `load_directory`.
- Once we support multiple snapshots, revisit whether `v_lease_detail`
  should expose all snapshots or just the latest — probably worth a
  parameterized function then.

---

## 2026-08-26 — Loader

Wrote `ingest/loader.py`, `ingest/cli.py`, `ingest/__main__.py`. `make load`
now populates the schema from all 50 files.

**Decisions**
- **One transaction per file.** A bad row in 462a shouldn't roll back the
  files loaded before it. Within a file, all-or-nothing.
- **SHA-256 hash as idempotency key**, stored in `source_file.file_hash`.
  Re-running `make load` skips files that have already been ingested. This
  is the honest answer to "what if we hand you next month's files?" — the
  same file bytes are a no-op; a genuinely new file (different bytes) loads.
- **Pre-validate charge codes.** If any parsed charge references a code not
  in `charge_code`, fail the whole file with a clear error rather than
  hitting a mid-transaction FK violation. Design rule was "unmapped code is
  a load-time error, never a silent `other`" — enforcing it at load time is
  strictly better than at query time.
- **Cross-report `lease_v_units` audits go in `ingest_audit`, keyed to the
  rent-roll snapshot**, not the availability snapshot. The check exercises
  the rent-roll parser primarily.

**Mistakes caught**
- **Cross-report audit ran on every invocation, doubling `lease_v_units`
  rows.** Symptom: after a second `make load` (which correctly skipped all
  50 files), audit count went 25 → 50. Root cause: I guarded the file loop
  on hash but not the cross-report step. Fix: only run cross-report audits
  if at least one file was actually loaded this invocation.
- **Typer collapses single-command apps.** Wrote `@app.command() def load(...)`
  expecting `python -m ingest load --dir ...` per the Makefile. Typer sees
  one command, flattens the app, and `load` becomes an unrecognised
  positional. Two options: add a dummy second command to force subcommand
  mode, or match reality. Chose the latter — updated the Makefile to
  `python -m ingest --dir $(DIR)`. When we add a second CLI command later,
  the current invocation will need to move back to a subcommand.

**Verified against the DB**
- `lease_total`: 4,106 / 4,106 pass.
- `charge_code`: 131 / 133 pass. The 2 failures are exactly the 462a
  SUBSIDY/SEC8CRD file-level offset (documented before this session).
- `lease_v_units`: 24 / 25 pass. The 1 failure is 153c (documented before
  this session).
- Re-run: 50 skipped, no double audit, exit 0.
- 115r status split reads 270/18/12/9 out of the DB, matching CLAUDE.md's
  canonical validation.

**Follow-ups**
- If we add another CLI command, re-introduce the subcommand structure and
  restore the Makefile to `python -m ingest load --dir $(DIR)`.
- Consider deleting-then-inserting `lease_v_units` on every run instead of
  guarding on "loaded > 0" — cleaner if snapshots get updated in place
  later.

---

## 2026-08-26 — Batch parser testing

Wrote `scripts/batch_parse.py`, added `make parse`. First thorough run of
both parsers against all 50 files.

**Decisions**
- **`make parse` exits 0 on file-level source oddities, non-zero on parser
  bugs.** The distinction matters: "our code is wrong" and "the source file
  is weird" want different responses. Split the exit signal so CI can catch
  regressions without being tripped by known Yardi quirks.
- **The strong per-property identity is `(current + notice + vacant) leases
  = total_units`**, not `(current + notice) = occupied`. The latter is
  informational only — commercial availability files leave state cells
  blank, so the identity legitimately fails there.

**Mistakes caught**
- **`ingest/parsers/__init__.py` imported from `.unit_avail`**; the file is
  `unit_availability.py`. Any caller doing `from ingest.parsers import ...`
  would have crashed at import. Silent because nothing had exercised the
  full import path until batch_parse.py did.
- **The rent-roll parser required both `unit_number` AND `unit_type` to
  recognise a lease row.** 153c is a commercial file where `unit_type` is
  blank on every row — silently dropped all 7 leases. Caught because
  batch_parse reported 0 leases against a summary block that said $3,476 in
  RENTRETL. Fix: also accept a lease row when col 0 (unit) + col 3
  (resident) are populated. Both `discover.py` and the parser had the same
  bug; the parser now correctly parses 7 leases.

**Discoveries (not parser bugs, file-level)**
- **462a summary block is internally inconsistent.** `SUBSIDY` reported
  $30,963, computed $32,273 (+$1,310). `SEC8CRD` reported −$30,963,
  computed −$32,273 (−$1,310). The two offset exactly, so the file's grand
  total still balances. Per-lease reconciliation on 462a passes for all
  269 leases, so trust the per-lease sum. Documented in `data_quality.md`.
- **153c cross-report gap.** Rent roll has 7 leases (1 occupied, 6 vacant).
  Availability report says `Units = 0`. The two Yardi exports disagree at
  the source. Occupancy for 153c must use `rent_roll_derived` — documented
  in `data_quality.md`.

**Follow-ups**
- Add these two source-file oddities to the eventual data-quality panel in
  the dashboard.
