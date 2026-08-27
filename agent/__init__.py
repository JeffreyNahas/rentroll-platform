"""Curated tool-use agent over the read-only API.

Sibling of `api/` and `web/` per `docs/architecture.md`'s data-flow
diagram. Tools call the running FastAPI server (`api/`) over HTTP -- the
agent has no direct database access -- so every answer inherits PII
masking, `sources`/`warnings`, and the sqlglot-guarded escape hatch for
free. See `docs/agent.md`.

The public entrypoint is `agent.run.answer()`, used by both
`api/agent_routes.py` (the dashboard's command dock) and, later, the
evals harness.
"""
