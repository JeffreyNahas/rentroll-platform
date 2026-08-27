"""FastAPI tool backend.

Seven modules on purpose: `app` (assembly), `db` (settings + two pools),
`envelope` (citations, warnings, PII), `routes` (typed GETs), `sql` (hatch),
`sql_guard` (AST checks, no FastAPI). Every query endpoint reads through
the `rri_readonly` role. The design rule "every metric carries its source"
is the required `sources` field in `api/envelope.py`.
"""
