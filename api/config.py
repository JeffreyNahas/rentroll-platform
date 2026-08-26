"""Runtime settings, read from environment via python-dotenv."""

from __future__ import annotations

import os

from dotenv import load_dotenv
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
