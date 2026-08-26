"""Apply SQL migrations in order, tracking which have already run.

Each file in db/migrations/ runs exactly once, inside a transaction.
Simpler than Alembic and enough for a schema that only moves forward.

    python -m ingest.migrate
"""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

MIGRATIONS = Path(__file__).resolve().parent.parent / "db" / "migrations"

TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migration (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def main() -> None:
    load_dotenv()
    dsn = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")

    with psycopg.connect(dsn) as conn:
        conn.execute(TRACKING_TABLE)
        conn.commit()

        applied = {row[0] for row in conn.execute("SELECT filename FROM schema_migration")}

        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in applied:
                print(f"  skip    {path.name}")
                continue
            print(f"  apply   {path.name}")
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute(
                    "INSERT INTO schema_migration (filename) VALUES (%s)", (path.name,)
                )

    print("migrations up to date")


if __name__ == "__main__":
    main()