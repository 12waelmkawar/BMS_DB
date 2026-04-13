"""
database.py — PostgreSQL schema initialisation and common query helpers.
Uses psycopg2 (synchronous) wrapped in a simple connection pool helper so
it can be called directly from FastAPI route handlers.
"""

import os
import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

load_dotenv()

_pool: ThreadedConnectionPool | None = None

DSN = (
    f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
    f"port={os.getenv('POSTGRES_PORT', '5432')} "
    f"dbname={os.getenv('POSTGRES_DB', 'bms_intelligence')} "
    f"user={os.getenv('POSTGRES_USER', 'bms_user')} "
    f"password={os.getenv('POSTGRES_PASSWORD', 'bms_password')}"
)

DDL = """
CREATE TABLE IF NOT EXISTS tc_results (
    id          SERIAL PRIMARY KEY,
    tc_id       TEXT NOT NULL,
    tc_name     TEXT,
    release     TEXT NOT NULL,
    sop         TEXT NOT NULL,
    domain      TEXT NOT NULL,
    result      TEXT NOT NULL,
    report_file TEXT,
    parsed_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tc_release
    ON tc_results(tc_id, release, sop);

CREATE TABLE IF NOT EXISTS jira_tickets (
    tc_id        TEXT PRIMARY KEY,
    jira_id      TEXT NOT NULL,
    status       TEXT NOT NULL,
    priority     TEXT,
    assignee     TEXT,
    fail_release TEXT,
    fix_release  TEXT,
    fix_status   TEXT,
    jira_url     TEXT,
    created_at   TIMESTAMPTZ,
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);
"""


def get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(1, 10, dsn=DSN)
    return _pool


def get_conn():
    """Acquire a connection from the pool (use as context manager)."""
    return _PooledConn(get_pool())


class _PooledConn:
    """Context manager that returns a connection to the pool on exit."""

    def __init__(self, pool: ThreadedConnectionPool):
        self._pool = pool
        self._conn = None

    def __enter__(self):
        self._conn = self._pool.getconn()
        self._conn.autocommit = False
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._pool.putconn(self._conn)
        return False


def init_db() -> None:
    """Create tables and indexes if they do not already exist."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)


def upsert_result(conn, row: dict) -> None:
    """Insert or update a test result (keyed on tc_id + release + sop)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tc_results (tc_id, tc_name, release, sop, domain, result, report_file)
            VALUES (%(tc_id)s, %(tc_name)s, %(release)s, %(sop)s, %(domain)s, %(result)s, %(report_file)s)
            ON CONFLICT (tc_id, release, sop) DO UPDATE SET
                tc_name     = EXCLUDED.tc_name,
                domain      = EXCLUDED.domain,
                result      = EXCLUDED.result,
                report_file = EXCLUDED.report_file,
                parsed_at   = NOW()
            """,
            row,
        )


def upsert_ticket(conn, row: dict) -> None:
    """Insert or update a Jira ticket row."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO jira_tickets
                (tc_id, jira_id, status, priority, assignee,
                 fail_release, fix_release, fix_status, jira_url, created_at)
            VALUES
                (%(tc_id)s, %(jira_id)s, %(status)s, %(priority)s, %(assignee)s,
                 %(fail_release)s, %(fix_release)s, %(fix_status)s, %(jira_url)s, %(created_at)s)
            ON CONFLICT (tc_id) DO UPDATE SET
                jira_id      = EXCLUDED.jira_id,
                status       = EXCLUDED.status,
                priority     = EXCLUDED.priority,
                assignee     = EXCLUDED.assignee,
                fail_release = EXCLUDED.fail_release,
                fix_release  = EXCLUDED.fix_release,
                fix_status   = EXCLUDED.fix_status,
                jira_url     = EXCLUDED.jira_url,
                updated_at   = NOW()
            """,
            row,
        )


def validate_fix(conn, tc_id: str, fix_release: str, sop: str) -> str:
    """Cross-check TC result in the claimed fix release."""
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            "SELECT result FROM tc_results WHERE tc_id=%s AND release=%s AND sop=%s",
            (tc_id, fix_release, sop),
        )
        row = cur.fetchone()
    if not row:
        return "FIX_PENDING"
    return "FIX_CONFIRMED" if row["result"] == "PASS" else "FIX_FAILED"


def revalidate_fix_claims(conn, release: str, sop: str) -> None:
    """Re-run fix validation for all tickets claiming a fix in the given release."""
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            "SELECT tc_id, fix_release FROM jira_tickets WHERE fix_release=%s",
            (release,),
        )
        tickets = cur.fetchall()
    for t in tickets:
        new_status = validate_fix(conn, t["tc_id"], t["fix_release"], sop)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jira_tickets SET fix_status=%s, updated_at=NOW() WHERE tc_id=%s",
                (new_status, t["tc_id"]),
            )
