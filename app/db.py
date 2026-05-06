"""
Postgres access layer.

Connection details come from DATABASE_URL (Render/Fly/Heroku style):
    postgres://user:pass@host:5432/dbname

Falls back to PGHOST/PGUSER/... for compose-style configs. The pool is
created lazily on first call so the app boots even when the DB is still
starting (the request itself will retry).
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


_pool: ConnectionPool | None = None
_SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def _conninfo() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # Render gives postgres://; psycopg wants postgresql://
        return url.replace("postgres://", "postgresql://", 1)
    # Fall back to PG* env vars (docker-compose style)
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    user = os.environ.get("PGUSER", "skylar")
    pwd  = os.environ.get("PGPASSWORD", "skylar")
    db   = os.environ.get("PGDATABASE", "skylar")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"


def pool() -> ConnectionPool:
    """Lazy-init the global connection pool. Idempotent."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=_conninfo(),
            min_size=1, max_size=10,
            timeout=20,
            kwargs={"row_factory": dict_row, "autocommit": True},
            open=True,
        )
    return _pool


def init_schema(retries: int = 30, delay: float = 1.0) -> None:
    """Apply schema.sql. Retries to tolerate Postgres still booting up."""
    sql = _SCHEMA_FILE.read_text()
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with pool().connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
            return
        except Exception as e:
            last_err = e
            time.sleep(delay)
    raise RuntimeError(f"DB schema init failed after {retries} attempts: {last_err}")


@contextmanager
def cursor() -> Iterator[psycopg.Cursor]:
    """Context-manager that yields a cursor on a pooled connection."""
    with pool().connection() as conn:
        with conn.cursor() as cur:
            yield cur


# ---------------------------------------------------------------------------
# Tiny query helpers — enough for our needs without an ORM
# ---------------------------------------------------------------------------
def fetch_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def fetch_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def execute(sql: str, params: tuple = ()) -> None:
    with cursor() as cur:
        cur.execute(sql, params)


def jsonify(value: Any) -> Any:
    """Wrap Python value as a JSONB-compatible parameter for psycopg."""
    if value is None:
        return None
    return psycopg.types.json.Json(value)
