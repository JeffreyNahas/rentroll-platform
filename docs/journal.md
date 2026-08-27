# Journal

Reverse-chronological session log. Each entry captures *why* a decision was
made and any mistake worth remembering. Facts about the *what* live in the
code; this file exists for the parts a `git log` doesn't tell you.

**Discipline:** one short entry per work session. Include mistakes and how
they were caught — silently fixing them loses the interview asset.

---

## 2026-08-27 — "How many units in total" and the temptation to loosen grounding

The agent failed closed on "how many units in total": it summed
`portfolio_summary`'s five per-type `total_units` values itself (4,006)
instead of reading a pre-computed total, so grounding correctly rejected
the self-computed figure. First instinct floated was to remove the
grounding check since it was "too strict to be usable." Pushed back:
that trades "annoyingly declines sometimes" for "confidently wrong
sometimes," which is a worse failure mode for a project whose whole
pitch is trustworthy numbers over messy data, and it doesn't even fix
the actual bug -- the model's naive sum was itself a worse number than
the source-reconciled one (see below). Landed on adding the missing
tool instead: `v_portfolio_totals` (migration 006), `GET
/portfolio/totals`, and a `portfolio_totals` agent tool.

**Decisions**
- **`total_units` and `total_rentable_units` are both exposed, not
  collapsed into one "total."** They're computed differently
  (availability-report raw count vs. `v_occupancy_by_property`'s
  source-reconciled, non-revenue-excluded figure) and differ by more
  than rounding -- 4,006 vs 4,000. Picking one silently would be the
  same mistake `occupancy_source` already exists to avoid for occupancy;
  a `unit_total_source_gap` warning does for units what
  `occupancy_source_fallback` does for occupancy.
- **Sums across property_type are fine; blended ratios are not.**
  Design rule #4 forbids averaging a percentage across incommensurable
  property types, not adding up plain counts. `v_portfolio_totals` sums
  additive counts only and deliberately has no occupancy-percentage
  column.

**Mistakes caught**
- **My first warning message overclaimed causation.** It said the
  portfolio-wide total_units/total_rentable_units gap (-6) "is the 153c
  gap" (+7). Queried the actual per-property breakdown before shipping
  the claim: the net portfolio-wide number is the combined effect of
  153c's +7 *and* six other properties' small negative
  non-revenue/unclassified exclusions, not attributable to one property.
  Caught by checking the SQL myself rather than trusting my own
  first-draft prose -- exactly the kind of unverified claim this
  project's numeric-grounding check exists to catch the *model* making,
  so it was worth catching in my own writing too.

## 2026-08-27 — Agent: curated toolbelt + numeric grounding

Built `agent/`, the tool-use layer the command dock was waiting for.
Named tools (one per API endpoint, `agent/tools.py`) call the *running*
FastAPI server over HTTP rather than the database directly, so every
answer inherits PII masking, `sources`/`warnings`, and the sqlglot guard
for free (CLAUDE.md rule #2). `POST /agent/ask` mounts into the existing
`api/` process; the command dock now actually asks it.

**Decisions**
- **Tools are HTTP calls to `api/`, not DB access.** `docs/api.md`
  already promised "the agent treats the same endpoints as tools" —
  taking that literally means zero new DB surface and zero new PII
  handling to get right a second time.
- **`httpx2`, not `httpx`.** This environment's `anthropic` package
  already depends on a vendored `httpx2`/`httpcore2` pair (same API,
  different import name) instead of standard `httpx`. Reused it rather
  than adding a second, real `httpx` dependency alongside a transitive
  one that does the same thing.
- **One retry, then fail closed.** `agent/grounding.py` extracts every
  number in the draft answer and checks it against every number
  anywhere in this turn's tool output (structured values *and* prose —
  an API-authored warning message that already says "7 properties" is a
  legitimate source for that figure). Ungrounded → one corrective retry
  → still ungrounded → the fixed sentence, per rule #1.

**Mistakes caught**
- **The plain-number regex re-matched fragments inside comma-grouped
  currency.** `$3,012` in a drafted answer was independently re-matched
  by the plain-number pattern starting just after the comma, yielding a
  spurious `012` → `12.0`, which doesn't exist in any tool result. This
  wrongly fired the fail-closed path on a fully correct answer. Caught by
  testing a real leases question end-to-end, not by unit tests written
  against my own assumptions. Fixed by masking currency/percent spans
  before running the plain-number pass.
- **Small identifiers coincidentally "ground" miscounted totals.** Asked
  the agent to break down properties by type; it tallied raw
  `list_properties` rows itself instead of reading
  `portfolio_summary.n_properties`, and miscounted (11 residential
  instead of 12). Grounding didn't catch it — `property_id` runs 1-25, so
  small hand-counted totals coincidentally matched *some* id in the same
  response and looked "grounded" even though they were wrong. Fixed two
  ways: `agent/grounding.py` now excludes any `*_id` field from the
  grounded-number pool, and the system prompt now says to prefer a
  pre-aggregated tool over tallying a row-level one. Neither guarantees
  correctness — grounding verifies a number *appeared*, not that it's the
  *right* number — that gap is exactly what the evals harness (next up)
  needs to measure across more than one model sample.

**Follow-ups**
- Evals harness (`TODO.md`) — `agent.run.answer()`'s signature was kept
  import-only and FastAPI-free specifically so evals can call it directly.
- Named-tool calls aren't written to `query_audit` yet (only the SQL
  escape hatch is, unchanged from before the agent existed);
  `query_audit.tool_name`/`question` are already generic enough to carry
  it if wanted later.
- Streaming responses, dynamic agent-authored charts.

---

## 2026-08-27 — Dashboard redesign: the engineering sheet

Replaced the dashboard's visual world. The brief was narrow — "green and
off-white, other colours for the charts" — but the incumbent look was a
scaffold default, so this was a replacement rather than a recolour.
`dashboard-app/` (Next 16) is now canonical; `web/` is superseded.

**Decisions**
- **The world is an engineering drawing sheet** — ISO/DIN title blocks on
  green-grid computation-pad stock. Chosen because the project's design
  rules map onto real drawing devices instead of being documented beside
  them: a title block *is* rule #3, a revision margin *is* rule #6, a
  hatched out-of-scope field *is* "by design, not by data loss", and one
  shared scale across the schedule *is* rule #4. Prose asserting those
  rules is worth less than a page whose anatomy enforces them.
- **Green stopped meaning "good."** It had been the `availability_report`
  badge colour. Once green became the ground it could no longer carry
  status, so status moved onto drawn marks (`Glyph.tsx`) with colour only
  confirming. This incidentally fixed a real accessibility defect: the old
  green-vs-amber badges conveyed occupancy source by colour alone.
- **Property type is keyed by hatch, not hue** — solid / ruled / diagonal /
  stipple / open, the way a plat or Sanborn map keys land use. Spending
  five hues on five badges would have left nothing for the data.
- **Tremor removed; every chart is hand-drawn CSS/SVG.** A stock chart
  library inside a committed world drags a second design system in — its
  rounded cards, its default blue, its type scale. The charts here are
  simple enough that hand-drawing them cost less than fighting the
  library, ships zero client JS, and deleted the 40-line Tailwind v4
  `@source inline()` safelist Tremor needed.
- **The charge-mix donut became a stacked bar.** Eight categories where
  base rent is ~90% is the textbook donut anti-pattern — seven unreadable
  slivers around one dominant arc. Base rent takes graphite rather than a
  series ink so the ~8% that actually varies is what gets the colour.
- **The agent's shell is a command line docked to the sheet's bottom
  edge.** A drafting application has always had one there. The input is
  genuinely disabled and says "toolbelt not connected"; a mocked chat that
  answered nothing would have been worse than an honest empty state.
- **Light only, deliberately.** The use scene is a narrated screen-share
  in a bright room and the material is paper. A lit pad has no dark mode;
  recorded as a commitment so nobody adds one as a chore.

**Mistakes caught**
- **The recorded validator receipt cited a surface the build never
  shipped.** The chart palette was validated against `#F2F1EA` while the
  shipped `--color-field` is `#f4f2e9`. Caught in review. Re-ran against
  the real token (it passes), and left the wrong figure visible in the
  comment as a disclosed error — on a project whose whole pitch is
  provenance, quietly overwriting a bad receipt is the wrong instinct.
- **Amber failed the contrast floor and I had already measured it.** I
  computed `#a8631c` at 4.19:1, wrote "use a darker one for text", then
  used it for 11px text in five places. Now `#955714` (5.1:1). Measuring
  and then not acting on the measurement is worse than not measuring.
- **Hidden tooltips widened the document.** `position: absolute` elements
  contribute to scroll width even at `opacity: 0`, giving the page a
  phantom horizontal scrollbar. Fixed with `display: none` plus
  `@starting-style` so the entrance animation survives.
- **The focus ring was falling back to the 1px UA outline** on `<summary>`,
  because the selector was a hand-listed set that missed it. Broadened to
  bare `:focus-visible`.
- **Full-page screenshots misrepresent `position: sticky`.** Once the dock
  was pinned, Chrome rendered it mid-document in `fullPage` captures — it
  read as a broken layout. Evidence for the sticky behaviour has to be a
  true-viewport capture; the full-page shots hold the dock static at
  capture time only.
- **Fixing one regression opened another.** Widening the property-name
  column on mobile pushed `% occ` out of view — re-breaking the exact rule
  the mobile column work existed to protect. Caught by measuring the table
  against its container at 360/375/390/414 instead of eyeballing one width.

**Process note**
Ran a finish review in a fresh context against the screenshots and code.
It returned `fix` with eight material findings — several of them fair hits
on claims the build made about itself. Applied all eight, recaptured, and
the verdict pass scored every one resolved plus two minor regressions,
which were then closed. The review is worth more than the build thread's
own self-checks precisely because it does not inherit the build's framing.

**Follow-ups**
- The schedule asserts "one shared scale" in prose but never draws a scale
  key; a printed key would make the claim verifiable rather than asserted.
- The deviations margin has no revision letter/date column — it is a
  revision *list*, not yet a revision *table*.
- Focus rings fade in over ~150ms on elements carrying `transition-colors`,
  which transitions `outline-color` from a layer that beats `base`. The
  clean fix is dropping `outline-color` from that utility.
- `web/` still exists. Delete it once the migration is confirmed.

---

## 2026-08-27 — Dashboard

Two-page Next.js + Tremor dashboard on top of the API. `make web` on
`:3000`; `make api` must be running.

**Decisions**
- **Two pages, no more.** Overview + Property detail. A dashboard with 12
  routes is harder to walk through than one with 2, and the story is
  linear: portfolio → property → row-level. No sidebar. No admin.
- **Server components everywhere, no client fetching library.** Each
  page is `async function Page() { const [a, b] = await Promise.all(...); }`.
  `revalidate: 60` on every fetch. Nothing to explain about hooks,
  loading spinners, or hydration. If a fetch is slow, the page is slow
  — measured trade-off; sub-10ms gold-view queries make it invisible.
- **Tremor over Recharts + hand-rolled CSS.** One dependency; KPI cards,
  charts, and tables come styled together. The chart set is limited —
  fine, the dashboard only uses three chart types.
- **Design rules made visible, not just documented.** `SourcesChip` next
  to every KPI; `OccupancySourceBadge` on every property row (green vs
  amber); data-quality panel at the bottom of Overview reads directly
  from `/portfolio/data-quality/failures` including the human-readable
  `note` for each row. A reviewer can point at the pixels and quote the
  CLAUDE.md rule number.
- **No blended portfolio occupancy %.** The KPI card is `264 / 296`, not
  `92%`. Rule #4 wants to be visible; leaving out the number is what
  makes it visible.

**Mistakes caught**
- **Function props across the Server → Client boundary.** Tremor's
  `BarChart` and `DonutChart` take `valueFormatter: (v: number) => string`.
  Passing that from a server component throws *"Functions cannot be
  passed directly to Client Components"*. Every chart now lives in its
  own thin `"use client"` wrapper (`PctBarChart`, `CountBarChart`,
  `ChargeMixDonut`); the server page only passes serializable data. This
  is the single most common gotcha when using Tremor from App Router —
  worth pointing at in the walkthrough.
- **Uvicorn started from wrong CWD.** After `cd web && npm install`, the
  shell CWD stayed in `web/`, and `uvicorn api.app:app` couldn't find
  the `api` module. Not a code issue; a "restart your terminal" issue.
  Documented so future-me doesn't chase it.

**Verified**
- `curl http://127.0.0.1:3005/` returns 200 with the property codes
  `462a`, `153c`, `134c`, `139c`, `143c` all present in the SSR-rendered
  HTML (data-quality panel is rendering).
- `/properties/115r` shows `availability_report` badge; `/properties/153c`
  shows `rent_roll_derived`.
- PII masking works — `Resident #N` present in the leases table HTML.
- `make api` + `make web` runs both without changes needed.

**Follow-ups**
- Bump Next.js: 14.2.15 has a known SSRF advisory (14.2.16+ patched).
  Localhost demo doesn't need it, but it's a one-line change before
  submission.
- If a chart looks too small on mobile, revisit the fixed h-72/h-40
  sizing — for the walkthrough on a laptop it's fine.
- The `webpack` warning about `recharts@2.15.4` is Tremor's transitive
  dep; upstream fix, not ours.

---

## 2026-08-27 — Flatten `api/` for the walkthrough

Fourteen files was textbook FastAPI layout, not extra capability. Collapsed
to seven modules so a reviewer can follow one request without bouncing:
`app`, `db` (settings + pools), `envelope` (citations + PII), `routes`
(typed GETs), `sql` (hatch), `sql_guard` (AST, no FastAPI). URLs and
response shapes unchanged. Dropped `python -m api` / `__main__.py` —
`make api` was already the entrypoint. `sql_guard.py` stays its own file
so the governance check is unit-testable without a server.

---

## 2026-08-26 — API polish (data-quality details, warnings, section filter)

Three complementary additions that make the design rules visible in
Postman without extra UI.

**Decisions**
- **Split data-quality into `/summary` (counts) + `/failures` (details)**,
  not a single mixed endpoint. Mixing summary rows and detail rows in one
  `data` array would break the uniform-schema envelope. Two clean
  endpoints, one for the tile, one for the panel.
- **Uniform row shape across failure kinds** — `check_name`,
  `property_code`, `subject`, `expected`, `actual`, `delta`, `note`.
  Callers don't have to switch on kind; the `note` is human-readable so a
  reviewer sees "462a summary of SUBSIDY reported $30,963 but leases sum
  to $32,273" instead of `audits_charge_code_fail: 2`. `unclassified_units`
  synthesised as if it were an audit row (`expected=0`, `actual=count`)
  so it slots into the same shape as `ingest_audit` failures.
- **Warnings use the field that was already there.** The envelope shipped
  with a `warnings: []` slot from day one. Populating it retrofits
  transparency onto existing endpoints — no route changes, no client
  changes, just more honest responses.
- **Migration 005: remove the `WHERE section = 'current'` from
  v_lease_detail** rather than adding a second view or querying `lease`
  directly in the router. Safe because every downstream view already
  filters on `lease_status IN ('current','notice')` which excludes
  `'future'`. `CREATE OR REPLACE VIEW` works because the column list is
  unchanged (only the WHERE clause is gone).
- **`?section=current|future` as a filter, not a `/pipeline` endpoint.**
  Same row schema serves both; a whole new route for 93 rows would be
  overbuilding.

**Verified**
- `/portfolio/data-quality/failures` → 6 rows (3 audit + 3 unclassified),
  each with the expected `note`.
- `/occupancy` (all) → warns about 7 fallback properties. Surprise: 3 of
  the 7 (134land, 183c, altapm) have `total_units=0`, so they trip the
  `AND total_units > 0` clause and fall to `rent_roll_derived` even
  though there's nothing to occupy. Correct, honest, worth being explicit
  about — the warning names them.
- `/loss-to-lease?property_type=commercial` → 0 rows + explicit warning.
- `/properties/144r/leases?section=future` → 32 future applicants, PII
  masked, `future_applicants` warning attached. Matches the batch-parse
  count for 144r.
- Migration 005: `v_lease_detail` went from 4013 → 4106 rows;
  `v_portfolio_summary_by_type` unchanged (still 3251 residential
  units).

**Follow-ups**
- Consider whether `/occupancy` should split the warning into "genuinely
  empty" (land, management) vs "fallback because of data anomaly" (153c
  and the three commercial). The current single warning is honest but a
  reviewer might read it as if 134land has a data problem.

---

## 2026-08-26 — FastAPI tool backend

Wrote the `api/` package: 12 endpoints (one per gold view + fat property
detail + paginated lease detail + guarded SQL escape hatch), all reading
through `rri_readonly`. `make api` runs it on `:8000` with `--reload`.
Full endpoint catalogue is in the new `docs/api.md`.

**Decisions**
- **Sync FastAPI, `psycopg_pool.ConnectionPool` (min 1, max 5).** Async
  psycopg is real, but the take-home concurrency ceiling is one dashboard
  + one demo user. Sync `def` handlers run in FastAPI's threadpool; the
  pool prevents per-request connect overhead. Reassess if latency shows up.
- **Two pools, split by role.** `readonly_conn()` → `rri_readonly`;
  `privileged_conn()` → `postgres`, used only to write `query_audit`. The
  physical separation makes it impossible for a query endpoint to
  accidentally read through a role that can also write.
- **`dict_row` factory everywhere.** FastAPI's default JSON encoder
  handles date / datetime / Decimal, so returning `list[dict]` from
  `conn.execute(...).fetchall()` skips a whole layer of Pydantic row
  models. Cost: `/docs` shows generic `object` for row shapes. Worth it.
- **Envelope as plain dict + dataclasses**, not `pydantic.BaseModel`
  generics. Pydantic generics play badly with FastAPI's OpenAPI generation
  in some versions, and the shape is stable enough that the dataclass +
  dict combination is fine.
- **Sources semantics.** Property-scoped endpoints cite exactly the files
  for those properties. Portfolio endpoints cite all 50. Considered a
  "sources summary" mode for portfolio to reduce envelope size (~6 KB),
  rejected: the honest answer to "where did this number come from" is a
  list of every contributing file.
- **`run_readonly_sql` guard: sqlglot AST walk.** Six checks in order —
  parse, single statement, root type, forbidden AST nodes (Insert/Update/…),
  forbidden function names (`pg_read_file`, `dblink`, `lo_import`, etc.),
  row-cap wrap. Row cap defaulted to **1,000** (from the plan discussion);
  revisit once evals show whether the agent trips it.
- **`query_audit` writes go through `privileged_conn()` in their own
  transaction** — a slow user query holding a connection doesn't delay
  the audit row, and rollback of the user query doesn't roll back the
  audit.
- **PII masking at serialization time**, one helper in `api/pii.py`,
  called only by `/properties/{code}/leases`. Kept `MASK_PII=true` as the
  default per the walkthrough discipline — demo with it on.
- **CORS opened for `localhost:3000` (Next.js) and `localhost:8501`
  (Streamlit)** so either presentation option works without config
  changes.

**Requirements drift discovered and half-fixed**
- `requirements.txt` listed `psycopg2-binary` but the actual code has
  been on `psycopg` 3 the whole time (`ingest/migrate.py`, the loader).
  Added `psycopg==3.3.4` and `psycopg-pool==3.3.1` explicitly. Left
  `psycopg2-binary` in place — nothing uses it but removing it is a
  separate decision.

**Mistakes caught**
- **Pydantic generics on the response model** — tried `ApiResponse[T]`
  first; FastAPI 0.141 + Pydantic 2.13 flagged the generic type as
  ambiguous when serializing to OpenAPI. Backed off to a dict envelope
  built by a helper. Same shape, cleaner types, one fewer moving part.
- **`sqlglot.exp.Command` catch** — my first cut of the guard didn't
  reject `CALL` / `DO` / arbitrary command nodes; sqlglot parses those
  into an `exp.Command` node. Added it to the reject list before smoke
  testing.
- **Decimals serialized as strings.** Pydantic v2 / FastAPI's default
  encoder emits `"6755.63"` (string) for a `NUMERIC` column, not
  `6755.63`. Every money and percentage field was string-typed on the
  wire. Caught the first time I tried to do arithmetic on a response
  (`sorted(..., key=lambda r: -r['total_balance_owed'])` → `TypeError:
  bad operand type for unary -: 'str'`). Fixed with a `_decimals_to_floats`
  walk in `envelope()` — strings out, numbers in. Currency here caps at
  12,2 which is well inside float64 precision. Precision-safe alternative
  would be a Numeric.js wrapper on the frontend; not worth the
  ergonomics tax.

**Verified**
- All five smoke queries against `/run-readonly-sql` produced the
  expected outcome and the expected `query_audit` row (allowed/blocked
  with the exact reason string).
- `/portfolio/summary` numbers reconcile to `v_portfolio_summary_by_type`
  exactly.
- `/occupancy?property_code=115r` shows `occupancy_source =
  availability_report`, 270 occupied of 300 rentable, sources narrowed to
  the two 115r files.
- `/properties/115r/leases?limit=3` returns `Resident #1`, `Resident #2`
  — PII masking works.
- `/portfolio/data-quality` surfaces the 3 known audit failures.

**Follow-ups**
- Move `psycopg2-binary` out of requirements.txt when we do a general
  dependency review — currently unused.
- Consider adding a `/properties/{code}/expirations` alias for
  convenience once the dashboard is real (it can already query
  `/expirations?property_code=…`).

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
