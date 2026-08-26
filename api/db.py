"""Two connection pools.

* `readonly_conn()` — everything the dashboard and (later) the agent read.
  Bound to `rri_readonly`; SELECT only; 5-second statement timeout enforced
  at the role level (migration 003).
* `privileged_conn()` — reserved for future write paths. Not used by any
  query endpoint. Kept separate so we never accidentally read through a
  role that can also write.

Rows come back as dicts by default so FastAPI can serialise them without a
Pydantic model per endpoint.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from api.config import settings

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
