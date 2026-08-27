"""Guarded SQL escape hatch.

Every request writes a row to `query_audit`, whether blocked or executed.
That's the point of an audit trail -- rejections are the interesting rows.

Provenance: arbitrary SQL can touch anything, so `sources` is `null` and a
warning entry is attached to the response envelope.

AST checks live in `api/sql_guard.py` so they can be unit-tested without
spinning up FastAPI.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api import sql_guard
from api.db import privileged_conn, readonly_conn, settings
from api.envelope import ApiWarning, envelope

router = APIRouter()


class SqlRequest(BaseModel):
    sql: str = Field(..., description="A single SELECT statement.")
    question: str | None = Field(
        None, description="Natural-language question this SQL answers (audit only)."
    )


def _log_audit(
    *,
    question: str | None,
    sql_text: str,
    row_count: int | None,
    latency_ms: int | None,
    blocked: bool,
    block_reason: str | None,
) -> None:
    """`query_audit` is a write, so use the privileged pool. Kept in its own
    transaction so a slow user query doesn't hold the audit row hostage."""
    with privileged_conn() as conn:
        conn.execute("""
            INSERT INTO query_audit (question, tool_name, generated_sql,
                                     row_count, latency_ms, blocked, block_reason)
            VALUES (%s, 'run_readonly_sql', %s, %s, %s, %s, %s)
        """, (question, sql_text, row_count, latency_ms, blocked, block_reason))


@router.post("/run-readonly-sql", summary="Governed SELECT escape hatch")
def run_readonly_sql(body: SqlRequest) -> dict:
    """Validated with sqlglot AST, wrapped with a row cap, executed via
    `rri_readonly` (5s statement timeout enforced at the role level).
    Blocked and executed calls both write to `query_audit`."""
    started = time.perf_counter()
    guard = sql_guard.validate(body.sql, row_cap=settings.row_cap_sql_escape)

    if isinstance(guard, sql_guard.GuardBlocked):
        _log_audit(
            question=body.question, sql_text=body.sql,
            row_count=None, latency_ms=0,
            blocked=True, block_reason=guard.reason,
        )
        raise HTTPException(400, detail={
            "blocked": True,
            "reason": guard.reason,
            "hint": "Only single SELECT/CTE statements allowed; row cap "
                    f"{settings.row_cap_sql_escape}; filesystem and admin "
                    "functions are rejected.",
        })

    try:
        with readonly_conn() as conn:
            rows = conn.execute(guard.wrapped_sql).fetchall()
    except Exception as exc:                      # noqa: BLE001
        # Most likely a statement_timeout (Postgres 57014) or a permission
        # denied. Log the failure and surface a clean 400.
        reason = str(exc).splitlines()[0]
        _log_audit(
            question=body.question, sql_text=body.sql,
            row_count=None,
            latency_ms=int((time.perf_counter() - started) * 1000),
            blocked=True, block_reason=reason,
        )
        raise HTTPException(400, detail={"blocked": True, "reason": reason})

    latency_ms = int((time.perf_counter() - started) * 1000)
    _log_audit(
        question=body.question, sql_text=body.sql,
        row_count=len(rows), latency_ms=latency_ms,
        blocked=False, block_reason=None,
    )

    warnings = [
        ApiWarning(
            code="unprovenanced",
            message="Response came from a user-supplied SQL query; per-source "
                    "citations are unavailable. Prefer typed endpoints when possible.",
        ),
    ]
    env = envelope(rows, sources=None, started_at=started, warnings=warnings)
    env["row_cap"] = settings.row_cap_sql_escape
    env["wrapped_sql"] = guard.wrapped_sql
    return env
