"""FastAPI app assembly.

    uvicorn api.app:app --reload --port 8000

Pools are opened on startup, closed on shutdown. Routers are mounted with
consistent prefixes/tags so `/docs` groups them sensibly.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.db import close_pools, open_pools, readonly_conn, settings
from api.routes import metrics, portfolio, properties
from api.sql import router as sql_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pools()
    try:
        yield
    finally:
        close_pools()


app = FastAPI(
    title="Rent Roll Intelligence API",
    version="0.1.0",
    description=(
        "Read-only API over the rent-roll semantic layer. Every response "
        "carries `sources` back to the file and snapshot the numbers came "
        "from. See docs/api.md for the endpoint catalogue and envelope shape."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── routers ───────────────────────────────────────────────────────────────
app.include_router(portfolio, prefix="/portfolio", tags=["portfolio"])
app.include_router(properties, prefix="/properties", tags=["properties"])
app.include_router(metrics, tags=["metrics"])
app.include_router(sql_router, tags=["sql"])


# ── health ────────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
def health() -> dict:
    started = time.perf_counter()
    with readonly_conn() as conn:
        version = conn.execute("SELECT version() AS v").fetchone()["v"]
        n_snapshots = conn.execute(
            "SELECT count(*) AS c FROM report_snapshot"
        ).fetchone()["c"]
    return {
        "status": "ok",
        "db_version": version.split(",")[0],
        "n_snapshots_loaded": n_snapshots,
        "mask_pii": settings.mask_pii,
        "query_time_ms": int((time.perf_counter() - started) * 1000),
    }
