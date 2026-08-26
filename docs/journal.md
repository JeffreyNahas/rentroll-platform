# Journal

Reverse-chronological session log. Each entry captures *why* a decision was
made and any mistake worth remembering. Facts about the *what* live in the
code; this file exists for the parts a `git log` doesn't tell you.

**Discipline:** one short entry per work session. Include mistakes and how
they were caught — silently fixing them loses the interview asset.

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
