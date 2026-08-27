# Status

Snapshot of "where we are." Read this at the start of a work session.

For upcoming work, see `TODO.md`.
For a log of past decisions and mistakes, see `docs/journal.md`.

---

## Shipped

| Component | Notes |
|---|---|
| `docker-compose.yml` | Postgres 16 + Adminer, healthchecked |
| `Makefile` | `up down reset migrate load discover parse api dashboard eval test lint` |
| `db/migrations/001_*` | Full schema DDL |
| `db/migrations/002_*` | 32 charge codes with categories |
| `db/migrations/003_*` | `rri_readonly` role, SELECT-only, 5s timeout |
| `ingest/migrate.py` | Migration runner |
| `ingest/normalize.py` | `to_money` (parens negatives), `to_date` (Excel serials), `property_type` |
| `ingest/models.py` | Pydantic records with date-order and vacancy validators |
| `ingest/parsers/` | Both parsers. 4,106 / 4,106 per-lease reconciliations exact, 0 warnings |
| `scripts/discover.py` | Structure validation across all 50 files. `make discover` |
| `scripts/batch_parse.py` | Parser + reconciliation batch test. `make parse` |
| `ingest/loader.py` + `cli.py` | `make load`. Idempotent by file hash |
| `db/migrations/004_gold_views.sql` | 9 gold views: `v_latest_snapshot`, `v_lease_detail`, `v_occupancy_by_property` (with `occupancy_source`), `v_loss_to_lease`, `v_delinquency_by_property`, `v_charge_mix_by_property`, `v_expirations_by_month`, `v_portfolio_summary_by_type`, `v_data_quality_summary`. All granted to `rri_readonly` |
| `api/` | FastAPI tool backend (`app`, `db`, `envelope`, `routes`, `sql`, `sql_guard`). `make api` on `:8000`. 13 endpoints — one per gold view (now including `/portfolio/totals`) + `/portfolio/data-quality/failures` (detailed rows with a `note`) + `/properties/{code}/leases?section=` (paginated, PII-masked) + guarded `POST /run-readonly-sql`. Two connection pools, response envelope with `sources` + `warnings`, sqlglot AST guard, `query_audit` logging. Full spec in `docs/api.md`. |
| `db/migrations/005_lease_detail_include_future.sql` | `v_lease_detail` no longer filters on `section` — future applicants now reachable through `/properties/{code}/leases?section=future`. Downstream views unaffected (they filter on `lease_status`). |
| `dashboard-app/` | **Canonical dashboard.** Next.js 16 + React 19 + Tailwind v4. `make dashboard` on `:3000`. Two pages: `/` (portfolio sheet — title block, 25-row property schedule with shared scale, occupancy by type, expirations stacked by type, revision margin) and `/properties/[code]` (title block, loss-to-lease or hatched out-of-scope panel, delinquency, charge mix, paginated leases table). Server components + `revalidate: 60`; `LeasesTable` and `CommandDock` (agent chat, see below) are the only client components. Tremor removed — every chart is hand-drawn CSS/SVG with no client JS. Full spec in `docs/dashboard.md`; visual system in `DESIGN.md`. |
| `agent/` | Curated tool-use agent (Anthropic SDK). One tool per API endpoint, calling the running FastAPI server over HTTP — no direct DB access, so every answer inherits PII masking, `sources`/`warnings`, and the sqlglot guard for free. Numeric grounding check (`agent/grounding.py`) verifies every figure in a draft answer against this turn's tool output; one retry, then fails closed with "I can't verify that figure from the data." Mounted as `POST /agent/ask` in `api/agent_routes.py`. The dashboard's command dock is now live. Full spec in `docs/agent.md`. |
| `db/migrations/006_portfolio_totals_view.sql` | `v_portfolio_totals` — one-row portfolio-wide grand totals (straight sums, never a blended ratio). New `GET /portfolio/totals` + `portfolio_totals` agent tool. Added because "how many units in total" had no legitimate grounded answer; `total_units` and `total_rentable_units` are both exposed because they disagree, with a `unit_total_source_gap` warning explaining why. |
| `evals/` | Golden question set (13 questions, `golden_set.py`) + two recorded metrics: tool trajectory (exact set match against `expected_tools`) and semantic response accuracy (LLM judge, `judge.py`, comparing the actual answer against a prose `expected_facts` brief via a forced tool call for structured output). `python -m evals.run` / `make eval` calls `agent.run.answer()` directly — no HTTP — and writes `evals/report.md` + `evals/report.json`. Single-sample per question; the agent's non-determinism means this is a snapshot, not a stable score (multi-sample scoring is `TODO.md`'s next item). |

## Loaded database state

After `make load` (as of the last work session):

| Table | Rows |
|---|---|
| `property` | 25 |
| `unit` | 4,013 |
| `unit_type` | 448 |
| `resident` | 3,923 |
| `lease` | 4,106 |
| `lease_charge` | 9,177 |
| `property_availability` | 25 |
| `source_file` / `report_snapshot` | 50 / 50 |
| `raw_row` (bronze) | 19,525 |
| `ingest_audit` | 4,264 (4,261 pass, 3 fail) |
| `ingest_error` | 0 |

The 3 audit failures are the known file-level source oddities documented in
`docs/data_quality.md`: 462a `SUBSIDY`, 462a `SEC8CRD`, 153c
`lease_v_units`. No parser bugs remain.

## Verified against gold views

- 115r: 288 occupied of 300 rentable, `occupancy_source = availability_report`.
  Base rent $754,322 (matches `docs/data_quality.md` line 191 to the cent).
- 153c: `occupancy_source = rent_roll_derived`, 1 occupied of 7 rentable
  (availability said 0 units; rent roll had 7).
- Portfolio: 12 residential / 6 affordable / 5 commercial / 1 land / 1 other.
- Commercial rentable_units (49) exceeds commercial total_units (42) by 7 —
  reflects the 153c source disagreement, not a view bug.
- `v_data_quality_summary` surfaces the 3 known audit failures.
- **Noteworthy:** 115r `loss_to_lease` is −$22,830 (−3.12%) — actuals *exceed*
  market. Yardi's Market Rent field appears to behave as a floor here, not
  an asking rent. Real business signal, not a bug.

## Verified against the API

- `GET /health` → `PostgreSQL 16.15`, 50 snapshots loaded, `mask_pii=true`.
- `GET /portfolio/summary` → 5 rows, matches gold view (12 res @ 92.13%, 6
  aff @ 93.68%, 5 comm @ 53.06%). Cites 50 sources.
- `GET /occupancy?property_code=115r` → `occupancy_source=availability_report`,
  270 occupied of 300 rentable. Cites 2 sources.
- `GET /occupancy` (all) → emits `occupancy_source_fallback` warning listing
  the 7 properties on rent-roll-derived source (134c, 134land, 139c, 143c,
  153c, 183c, altapm).
- `GET /loss-to-lease?property_type=commercial` → empty result + explicit
  `loss_to_lease_out_of_scope` warning ("by design, not by data loss").
- `GET /portfolio/data-quality/failures` → 6 rows: 3 audit failures
  (462a SUBSIDY, 462a SEC8CRD, 153c cross-report) + 3 unclassified rollups
  (134c=3, 139c=10, 143c=4). Every row carries a human-readable `note`.
- `GET /properties/144r/leases?section=future&limit=3` → 32 total future
  applicants, PII masked, `future_applicants` warning attached.
- `GET /properties/115r/leases?limit=3` → 300 total current-section, PII
  correctly masked (`Resident #1`, `Resident #2`).
- `POST /run-readonly-sql` — all guard paths exercised:
  valid SELECT → executed; `INSERT` → blocked ("only SELECT allowed");
  `pg_read_file('/etc/passwd')` → blocked ("forbidden function");
  `SELECT 1; DROP TABLE property;` → blocked ("multiple statements");
  `WITH … SELECT` → executed. All 5 attempts written to `query_audit`.

## Verified against the dashboard

- `make api` + `make dashboard`, browse to `:3000`.
- Overview renders 200 with: 5 KPI cards (no blended occupancy %, rule
  #4), occupancy-by-type bar chart, expirations next-12-months chart,
  properties table with `TypeBadge` + `OccupancySourceBadge` per row,
  data-quality panel showing all 6 failure rows with human notes.
- `/properties/115r` — availability_report badge (green), full KPI row,
  loss-to-lease with negative-delta explanation, charge mix donut,
  Resident #N in the leases table.
- `/properties/153c` — rent_roll_derived badge (amber), same layout,
  warnings inline explaining why the fallback source is used.
- `/properties/144r?section=future` — 32 future applicants render,
  `future_applicants` warning attached.

## Verified after the redesign (dashboard-app)

- All five inspected viewports report **0px horizontal overflow**
  (1440×900 and 390×844 on both pages, plus 153c commercial).
- Production build succeeds; the direction contract survives it and is
  greppable in `.next/server` by its seed key `c0872ef5`.
- Leases pagination works end to end: 1–100 → 101–200 → Next disabled on
  the last page; `offset` round-trips through the URL. No console errors.
- Contrast: every text token ≥4.5:1 on the sheet; `--color-ink-faint`
  (2.9:1) is used for non-text only. Chart palette re-validated against
  the shipped surface `#f4f2e9`.
- Charge mix on 115r reads $754,322 base rent at 92.5% — still matching
  `docs/data_quality.md` to the cent after the chart was rebuilt by hand.
- `DESIGN.md` written from the built code (ground truth, not the direction
  contract's intent). `.impeccable/` is the design-QA tool's local cache
  (session state, review screenshots) — gitignored, not a deliverable.
  One drift caught in the
  process: `TitleBlock`'s `Field` cells no longer use the `.tb-field` CSS
  class defined in `globals.css` — they moved to inline utility classes
  during the mobile-column fix, leaving `.tb-field` dead. Flagged, not
  silently removed; see `TODO.md`.

## Verified against the agent

- `POST /agent/ask` "which properties are on a rent-roll-derived
  occupancy source, and why?" → names the same 7 properties as the
  `/occupancy` API check above, citing `occupancy_source_fallback`, one
  tool call (`occupancy`).
- Cross-type blended-occupancy question → declines per rule #4, reports
  figures by type instead of inventing a portfolio-wide average.
- Leases + resident-name question on 115r → `Resident #1`/`Resident #2`
  throughout; `MASK_PII` holds end-to-end through the agent, not just the
  API.
- Fail-closed path verified directly (mocked an ungrounded model draft):
  returns the exact required sentence, not a hedge.
- Three real bugs caught and fixed while testing live — see
  `docs/journal.md` 2026-08-27 entries: a regex fragment-matching bug in
  the grounding check, small identifiers (`property_id`) coincidentally
  "grounding" a miscounted total, and percentages being compared against
  the wrong scale (a *correct* "78.15%" failed grounding against the raw
  0.7815 fraction, while a wrong "0.78%" would have passed).
- `GET /portfolio/totals` added after "how many units in total" had no
  legitimate grounded answer — see migration 006.
- **Streaming + inline citations shipped.** `POST /agent/ask/stream`
  (SSE) yields `tool_start`/`tool_done`/`status`/`error` progress events
  as the tool-use loop runs, then one terminal `done` event — progress
  only, the answer text itself is never token-streamed (it can still be
  discarded by grounding and replaced with the fail-closed sentence).
  `agent.run.answer()` is now a thin wrapper around `answer_stream()` —
  one implementation, not two. System prompt rule #8 has the model cite
  inline (`(property_code, report_type, as of date)`) right after each
  figure; verified live on both a single-property question ("Occupancy
  for 115r is 90% (115r, availability report, as of 2026-02-25)") and a
  portfolio-wide one (cites report types + date generally instead of 25
  properties). `CommandDock`'s transcript panel is now hand-drag
  resizable, height persisted per-viewer in `localStorage`.

## Verified against evals

- `make eval` end to end, 13/13 golden questions: 11/13 tool trajectory,
  13/13 semantic accuracy (after fixes below). The two trajectory
  "failures" are the agent reasonably calling one extra tool (e.g.
  `list_properties` alongside `loss_to_lease`) — not a bug, just stricter
  than exact-set-equality scoring allows; noted, not chased in this pass.
- **Two real bugs found and fixed by the harness itself, immediately** —
  see `docs/journal.md` 2026-08-28: accounting-notation negative numbers
  (`($12,006.39)`) were read as positive by the grounding check, and the
  model was inventing illustrative example numbers ("e.g. Resident #42")
  that correctly failed grounding since they weren't real. First one
  fixed in `agent/grounding.py`; second fixed with a one-line addition to
  the system prompt (`agent/prompts.py`) rather than special-casing the
  checker.

## Immediate next step

**Dynamic dashboards.** Chart-spec tool the agent invokes; Vega-Lite or
similar; pin to a canvas; PNG/CSV/PDF export. See `TODO.md` and
`docs/journal.md` for the existing plan sketch.
