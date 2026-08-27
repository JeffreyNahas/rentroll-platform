# TODO

Prioritized backlog. Top item is the next thing to work on. Cross items
off as they land (delete or move to `docs/journal.md`).

For what's already shipped, see `STATUS.md`.
For the interview-facing view, see `docs/walkthrough.md`.

---

## Next

- [ ] **Agent.** Curated read-only toolbelt (one tool per API endpoint),
  Anthropic SDK tool use, numeric grounding check that fails closed on
  unverifiable figures, `query_audit` on every call. Chat pane on the
  dashboard shell.

## After that
- [ ] **Evals.** Golden question set, tool-trajectory scoring, exact numeric
  checks, `evals/report.md`.
- [ ] **Dynamic dashboards.** Chart-spec tool the agent invokes; Vega-Lite
  or similar; pin to a canvas; PNG/CSV/PDF export. Plan in
  `docs/journal.md`.
- [ ] **Tests.** Synthetic fixtures for the parsers (never real files),
  parser unit tests, loader integration test against a scratch DB.
- [ ] **README.** Quickstart, ERD, data-quality summary, eval results.

## Nice-to-have (not on critical path)

- [ ] Delete `web/` once the `dashboard-app/` migration is confirmed.
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
- [ ] `dashboard-app/src/components/ui/{card,badge,button}.tsx` are
  unused scaffold leftovers (the redesign's own components replaced them),
  as are the `lucide-react` and `next-themes` dependencies. Confirmed via
  grep — zero imports of either. Remove both the files and the deps once
  someone's ready to touch `package.json` again.

- [ ] Re-introduce typer subcommand structure once a second CLI command
  exists; restore Makefile `python -m ingest load --dir $(DIR)`.
- [ ] Consider delete-then-insert for `lease_v_units` audits instead of the
  current guard-on-loaded pattern.
