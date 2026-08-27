"""Settings and two connection pools.

* `readonly_conn()` — everything the dashboard and (later) the agent read.
  Bound to `rri_readonly`; SELECT only; 5-second statement timeout enforced
  at the role level (migration 003).
* `privileged_conn()` — writes to `query_audit` from the escape hatch.
  Kept separate so we never accidentally read through a role that can
  also write.

Rows come back as dicts by default so FastAPI can serialise them without a
Pydantic model per endpoint.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from dotenv import load_dotenv
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

load_dotenv()


def _psycopg_dsn(url: str) -> str:
    """.env uses SQLAlchemy-style DSNs; psycopg wants the driverless form."""
    return url.replace("postgresql+psycopg://", "postgresql://")


class Settings(BaseModel):
    database_url: str
    readonly_database_url: str
    mask_pii: bool = True
    cors_origins: list[str] = [
        "http://localhost:3000",   # Next.js dev
        "http://localhost:8501",   # Streamlit dev
    ]
    # run_readonly_sql row cap. 1,000 accommodates a full residential drill;
    # smaller forces the agent to aggregate. Revisit once evals show whether
    # the agent trips the cap.
    row_cap_sql_escape: int = 1000
    # psycopg_pool sizing. Each request checks out one connection.
    pool_min_size: int = 1
    pool_max_size: int = 5


def _load() -> Settings:
    return Settings(
        database_url=_psycopg_dsn(os.environ["DATABASE_URL"]),
        readonly_database_url=_psycopg_dsn(os.environ["READONLY_DATABASE_URL"]),
        mask_pii=os.environ.get("MASK_PII", "true").lower() == "true",
    )


settings = _load()

_privileged_pool: ConnectionPool | None = None
_readonly_pool: ConnectionPool | None = None


def open_pools() -> None:
    global _privileged_pool, _readonly_pool
    _privileged_pool = ConnectionPool(
        settings.database_url,
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
        kwargs={"row_factory": dict_row},
        open=True,
    )
    _readonly_pool = ConnectionPool(
        settings.readonly_database_url,
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
        kwargs={"row_factory": dict_row},
        open=True,
    )


def close_pools() -> None:
    global _privileged_pool, _readonly_pool
    if _readonly_pool is not None:
        _readonly_pool.close()
        _readonly_pool = None
    if _privileged_pool is not None:
        _privileged_pool.close()
        _privileged_pool = None


@contextmanager
def readonly_conn() -> Iterator[Connection]:
    if _readonly_pool is None:
        raise RuntimeError("readonly pool not initialised; call open_pools() first")
    with _readonly_pool.connection() as conn:
        yield conn


@contextmanager
def privileged_conn() -> Iterator[Connection]:
    if _privileged_pool is None:
        raise RuntimeError("privileged pool not initialised; call open_pools() first")
    with _privileged_pool.connection() as conn:
        yield conn
