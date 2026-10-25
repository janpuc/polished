"""SQLite access: one connection per request, plus a transaction helper.

All SQL lives in the domain modules, which take a connection. The schema comes from
polished/migrations/, which the init container applies.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import Request


def connect(path: str) -> sqlite3.Connection:
    """Autocommit connection (WAL, foreign keys on); use transaction() to group writes."""
    # check_same_thread is off because a request's dependency setup and teardown may run on
    # different threadpool threads; a connection is still only used by one request at a time.
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma journal_mode = wal")
    conn.execute("pragma foreign_keys = on")
    conn.execute("pragma busy_timeout = 5000")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """begin immediate ... commit, or rollback if the block raises."""
    conn.execute("begin immediate")
    try:
        yield conn
    except BaseException:
        conn.execute("rollback")
        raise
    conn.execute("commit")


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: a connection for the length of one request."""
    conn = connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def schema_version(conn: sqlite3.Connection) -> int:
    """Highest applied migration, 0 on a database that was never migrated."""
    try:
        row = conn.execute("select max(version) from schema_version").fetchone()
    except sqlite3.OperationalError:
        return 0
    return row[0] or 0
