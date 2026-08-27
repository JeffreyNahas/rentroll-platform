# TODO

Prioritized backlog. Top item is the next thing to work on. Cross items
off as they land (delete or move to `docs/journal.md`).

For what's already shipped, see `STATUS.md`.
For the interview-facing view, see `docs/walkthrough.md`.

---

## Next

- [ ] **Dynamic dashboards.** Chart-spec tool the agent invokes; Vega-Lite
  or similar; pin to a canvas; PNG/CSV/PDF export. Plan in
  `docs/journal.md`.

## After that
- [ ] **Tests.** Synthetic fixtures for the parsers (never real files),
  parser unit tests, loader integration test against a scratch DB.
- [ ] **README.** Quickstart, ERD, data-quality summary, eval results.
- [ ] **Multi-sample evals.** Run each golden question N times, report a
  pass rate instead of a single-sample pass/fail -- the agent is
  non-deterministic (default temperature) and this session directly
  observed a question's tool choice and phrasing both varying run to
  run. See `evals/run.py`.

## Nice-to-have (not on critical path)

- [ ] Draw a printed scale key on the property schedule — it claims "one
  shared scale" in prose without ever drawing one.
- [ ] Give the deviations margin a revision letter/date column, so it is a
  revision *table* rather than a revision *list*.
- [ ] Delete `.tb-field` from `dashboard-app/src/app/globals.css` — dead CSS.
  `TitleBlock`'s `Field` moved to inline utility classes during the mobile
  layout fix and never removed the now-unused rule. Caught writing
  `DESIGN.md`.
- [ ] Add `dashboard` to the `.PHONY` line in `makefile` (currently lists
  `api web` but not the newer `dashboard` target — harmless, but drifted).

- [ ] Re-introduce typer subcommand structure once a second CLI command
  exists; restore Makefile `python -m ingest load --dir $(DIR)`.
- [ ] Consider delete-then-insert for `lease_v_units` audits instead of the
  current guard-on-loaded pattern.
- [ ] Write named-tool calls to `query_audit` (currently only the SQL
  escape hatch does). `tool_name`/`question` columns are already generic
  enough; `agent/run.py`'s `tool_calls` trace covers the response-side
  audit need for now. See `docs/agent.md`.
