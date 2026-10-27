"""
Digital Dukan - Utilities Module
Provides database connection management, connection pooling, and reusable helpers.
Uses raw MySQL connections with mysql-connector-python and dictionary cursors.
"""
from flask import g, has_app_context
import mysql.connector
from mysql.connector import pooling, Error
from config import Config

# Module-level connection pool
_db_pool = None


def get_db_pool():
    """
    Get or initialize the reusable MySQL connection pool.
    """
    global _db_pool
    if _db_pool is None:
        db_config = Config.get_db_config(include_db=True)
        _db_pool = pooling.MySQLConnectionPool(
            pool_name=Config.DB_POOL_NAME,
            pool_size=Config.DB_POOL_SIZE,
            **db_config
        )
    return _db_pool


def get_db_connection(use_pool=True):
    """
    Obtain a reusable MySQL database connection.
    When running within an active Flask application/request context, reuses `g.db`
    to guarantee a single connection per request and clean teardown on completion.
    """
    if has_app_context():
        if 'db' not in g or g.db is None or not g.db.is_connected():
            if use_pool:
                try:
                    pool = get_db_pool()
                    g.db = pool.get_connection()
                except Exception:
                    db_config = Config.get_db_config(include_db=True)
                    g.db = mysql.connector.connect(**db_config)
            else:
                db_config = Config.get_db_config(include_db=True)
                g.db = mysql.connector.connect(**db_config)
        return g.db

    # Standalone execution (outside Flask context)
    if use_pool:
        try:
            pool = get_db_pool()
            return pool.get_connection()
        except Exception:
            pass

    db_config = Config.get_db_config(include_db=True)
    return mysql.connector.connect(**db_config)


def get_db_cursor(conn=None, dictionary=True):
    """
    Get a database cursor with dictionary=True by default so rows
    are returned as Python dictionaries.
    Retains a strong reference to the connection on the cursor object.
    """
    if conn is None:
        conn = get_db_connection()
    cursor = conn.cursor(dictionary=dictionary)
    # Retain connection reference to prevent garbage collection during standalone usage
    cursor._connection_ref = conn
    return cursor


def close_db_connection(e=None):
    """
    Flask teardown handler to close the request-scoped database connection.
    For pooled connections, calling close() returns the connection back to the pool.
    """
    if has_app_context():
        db = g.pop('db', None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
