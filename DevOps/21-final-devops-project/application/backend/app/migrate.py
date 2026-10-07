"""Wait for PostgreSQL, take an advisory lock, run `alembic upgrade head`.

Runs as the Kubernetes initContainer (and before uvicorn in docker compose).
The advisory lock makes it safe when several replicas start at the same time.
"""

import sys
import time

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from .config import settings

LOCK_ID = 2110151  # arbitrary, constant across replicas


def main(timeout: int = 90) -> int:
    engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            conn = engine.connect()
            break
        except Exception as exc:  # noqa: BLE001
            if time.monotonic() > deadline:
                print(f"database not reachable after {timeout}s: {exc}", file=sys.stderr)
                return 1
            print("waiting for database ...", flush=True)
            time.sleep(3)
    with conn:
        is_pg = conn.dialect.name == "postgresql"
        if is_pg:
            conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": LOCK_ID})
        try:
            cfg = Config("alembic.ini")
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
            conn.commit()
            print("migrations applied (alembic head)", flush=True)
        finally:
            if is_pg:
                conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
                conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
