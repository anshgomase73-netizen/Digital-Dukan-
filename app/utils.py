"""
Digital Dukan - Utilities Module
Provides SQLite database connection management and reusable helpers.
Uses Python's built-in sqlite3 with sqlite3.Row row factory for zero-configuration deployment.
"""
import sqlite3
import datetime
from flask import g, has_app_context
from config import Config


# Register custom datetime/timestamp converters for sqlite3
def _convert_timestamp(val):
    if not val:
        return None
    s = val.decode('utf-8') if isinstance(val, bytes) else str(val)
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return s


sqlite3.register_converter('timestamp', _convert_timestamp)
sqlite3.register_converter('datetime', _convert_timestamp)


class DictRow(sqlite3.Row):
    """
    Subclass of sqlite3.Row providing dictionary-like .get() access
    while maintaining full sqlite3.Row index and name access.
    """
    def get(self, key, default=None):
        try:
            return self[key]
        except (IndexError, KeyError):
            return default


class SQLiteConnection(sqlite3.Connection):
    """
    Subclass of sqlite3.Connection that gracefully accepts cursor(dictionary=True)
    for seamless backward compatibility with existing code.
    """
    def cursor(self, *args, **kwargs):
        kwargs.pop('dictionary', None)
        return super().cursor(*args, **kwargs)


def get_db_connection(db_path=None):
    """
    Obtain a SQLite database connection to digital_dukan.db.
    When running within an active Flask application/request context, reuses `g.db`
    to guarantee a single connection per request and clean teardown on completion.
    Configures sqlite3.Row as the row_factory so queries return dictionary-like objects.
    Enforces foreign key constraints using PRAGMA foreign_keys = ON.
    """
    target_path = str(db_path or Config.DB_PATH)

    if has_app_context():
        if 'db' not in g or g.db is None:
            conn = sqlite3.connect(
                target_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                factory=SQLiteConnection
            )
            conn.row_factory = DictRow
            conn.execute("PRAGMA foreign_keys = ON;")
            g.db = conn
        return g.db

    # Standalone execution (outside Flask context)
    conn = sqlite3.connect(
        target_path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        factory=SQLiteConnection
    )
    conn.row_factory = DictRow
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_db_cursor(conn=None, dictionary=True):
    """
    Get a database cursor.
    Maintains compatibility with callers passing dictionary=True.
    """
    if conn is None:
        conn = get_db_connection()
    return conn.cursor()


def close_db_connection(e=None):
    """
    Flask teardown handler to close the request-scoped database connection.
    """
    if has_app_context():
        db = g.pop('db', None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
