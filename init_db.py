"""
Digital Dukan - Database Initialization Utility (SQLite)
Creates the digital_dukan.db database file and executes database_setup.sql.
Zero-configuration deployment ready for local development and PythonAnywhere.
"""
import sys
import sqlite3
from pathlib import Path
from config import Config


def initialize_database():
    """Create digital_dukan.db SQLite database and tables defined in database_setup.sql."""
    db_path = Config.DB_PATH
    print(f"Initializing SQLite database at: {db_path}...")

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    sql_file_path = Path(__file__).resolve().parent / 'database_setup.sql'
    if not sql_file_path.exists():
        print(f"[ERROR] SQL setup script not found at: {sql_file_path}")
        sys.exit(1)

    with open(sql_file_path, 'r', encoding='utf-8') as sql_file:
        sql_content = sql_file.read()

    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON;")

        # Execute full schema setup
        conn.executescript(sql_content)
        conn.commit()

        # Verify created tables
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
        tables = [row[0] for row in cursor.fetchall()]

        print("\nSQLite database initialization completed successfully!")
        print(f"Database file: {db_path}")
        print("Verified tables:")
        for tbl in tables:
            print(f"  - {tbl}")

        cursor.close()

    except sqlite3.Error as err:
        print(f"\n[DATABASE ERROR] SQLite initialization failed: {err}")
        sys.exit(1)
    except Exception as ex:
        print(f"\n[UNEXPECTED ERROR] {ex}")
        sys.exit(1)
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed cleanly.\n")


if __name__ == '__main__':
    initialize_database()
