"""AST-level validation for the run_readonly_sql escape hatch.

Order of enforcement (any failure short-circuits with a specific reason):

  1. Parse with sqlglot (Postgres dialect).
  2. Must be exactly one statement.
  3. Root expression must be a Select (or a CTE wrapping one).
  4. No forbidden function names (filesystem, network, or replication
     escape paths). Reject on any match while walking the AST.
  5. Wrap in `SELECT * FROM (…) _guarded LIMIT <cap>` so the row cap is
     enforced regardless of what the user asks for.

Read-only role + 5s statement timeout are enforced at the connection layer
(migration 003); this file exists to fail fast on things the role can
technically execute but shouldn't (e.g. `pg_read_server_files`).
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp


# Function names that read the filesystem, bridge to other databases, or
# access replication internals. Even a read-only role can invoke some of
# these; the AST check makes the guard explicit.
FORBIDDEN_FUNCTIONS = frozenset({
    "pg_read_file",
    "pg_read_binary_file",
    "pg_read_server_files",
    "pg_ls_dir",
    "pg_stat_file",
    "lo_import",
    "lo_export",
    "dblink",
    "dblink_exec",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "current_setting",       # can leak connection settings; not needed for read
    "set_config",             # writes settings
})


@dataclass
class GuardOk:
    wrapped_sql: str


@dataclass
class GuardBlocked:
    reason: str


GuardResult = GuardOk | GuardBlocked


def validate(sql_text: str, *, row_cap: int) -> GuardResult:
    """Return GuardOk(wrapped_sql) or GuardBlocked(reason)."""
    stripped = sql_text.strip().rstrip(";").strip()
    if not stripped:
        return GuardBlocked("empty query")

    try:
        parsed = sqlglot.parse(stripped, read="postgres")
    except sqlglot.errors.ParseError as exc:
        return GuardBlocked(f"parse error: {exc}")

    parsed = [p for p in parsed if p is not None]
    if len(parsed) != 1:
        return GuardBlocked("multiple statements not allowed")

    stmt = parsed[0]
    if not isinstance(stmt, (exp.Select, exp.With, exp.Subquery, exp.Union)):
        return GuardBlocked(
            f"only SELECT (or CTE wrapping SELECT) allowed; got {type(stmt).__name__}"
        )

    # Even a With/Union must ultimately be a SELECT tree. sqlglot's Query
    # protocol covers Select, Union, With -- but not DML wrapped in a CTE.
    for node in stmt.walk():
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Merge,
                             exp.Drop, exp.Create, exp.Alter, exp.TruncateTable,
                             exp.Grant, exp.Command)):
            return GuardBlocked(
                f"disallowed statement type in AST: {type(node).__name__}"
            )
        if isinstance(node, exp.Anonymous):
            name = (node.this or "").lower()
            if name in FORBIDDEN_FUNCTIONS:
                return GuardBlocked(f"forbidden function: {name}")
        if isinstance(node, exp.Func):
            name = type(node).__name__.lower()
            if name in FORBIDDEN_FUNCTIONS:
                return GuardBlocked(f"forbidden function: {name}")

    wrapped = f"SELECT * FROM ({stripped}) AS _guarded LIMIT {row_cap}"
    return GuardOk(wrapped)
