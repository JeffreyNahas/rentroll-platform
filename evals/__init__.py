"""Evals: golden question set, tool-trajectory + semantic-accuracy scoring.

Sibling of `agent/` and `api/` per `docs/architecture.md`'s data-flow
diagram. Calls `agent.run.answer()` directly -- no HTTP hop, no server
needed beyond the running FastAPI backend the agent's tools call.

Run with `make eval` (`python -m evals.run`). See `evals/run.py`.
"""
