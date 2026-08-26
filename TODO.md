# TODO

Prioritized backlog. Top item is the next thing to work on. Cross items
off as they land (delete or move to `docs/journal.md`).

For what's already shipped, see `STATUS.md`.
For the interview-facing view, see `docs/walkthrough.md`.

---

## Next

- [ ] **FastAPI tool backend.** One endpoint per gold view + a guarded
  `run_readonly_sql` escape hatch (sqlglot AST validation, `rri_readonly`
  role, row cap, 5s timeout, full `query_audit` logging). Every response
  carries a `sources` block back to file and row.

## After that
- [ ] **Presentation layer.** Next.js + TS preferred (hits the JD stack and
  patches a stated gap); Streamlit is the time-boxed fallback. Data-quality
  panel that surfaces `ingest_audit` failures and `unclassified_units`.
- [ ] **Agent.** Curated read-only toolbelt, sqlglot AST guard,
  `rri_readonly` role, citations, numeric grounding check that verifies
  every figure in the response appeared in tool output.
- [ ] **Evals.** Golden question set, tool-trajectory scoring, exact numeric
  checks, `evals/report.md`.
- [ ] **Tests.** Synthetic fixtures for the parsers (never real files),
  parser unit tests, loader integration test against a scratch DB.
- [ ] **README.** Quickstart, ERD, data-quality summary, eval results.

## Nice-to-have (not on critical path)

- [ ] Re-introduce typer subcommand structure once a second CLI command
  exists; restore Makefile `python -m ingest load --dir $(DIR)`.
- [ ] Consider delete-then-insert for `lease_v_units` audits instead of the
  current guard-on-loaded pattern.
