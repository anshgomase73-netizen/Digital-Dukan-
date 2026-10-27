"""
Digital Dukan - Database Initialization Utility
Connects to MySQL server, ensures database exists, and executes database_setup.sql.
Uses raw mysql.connector with dictionary=True cursors and comprehensive error handling.
"""
import sys
from pathlib import Path
import mysql.connector
from mysql.connector import errorcode
from config import Config


def initialize_database():
    """Create database and tables defined in database_setup.sql."""
    # 1. Validate credentials
    if not Config.DB_HOST or not Config.DB_USER:
        print("[ERROR] Missing database configuration! Please ensure DB_HOST and DB_USER are defined in your .env file.")
        sys.exit(1)

    print(f"Connecting to MySQL server at {Config.DB_HOST}:{Config.DB_PORT} as user '{Config.DB_USER}'...")

    conn = None
    try:
        # 2. Connect to MySQL server (without specifying DB so we can create it if needed)
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
        )

        cursor = conn.cursor(dictionary=True)

        # 3. Create database if it doesn't exist
        db_name = Config.DB_NAME or 'digital_dukan'
        print(f"Creating database '{db_name}' if not exists...")
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        cursor.execute(f"USE `{db_name}`;")
        print(f"Switched to database '{db_name}'.")

        # 4. Read database_setup.sql
        sql_file_path = Path(__file__).resolve().parent / 'database_setup.sql'
        if not sql_file_path.exists():
            print(f"[ERROR] SQL setup script not found at: {sql_file_path}")
            sys.exit(1)

        with open(sql_file_path, 'r', encoding='utf-8') as sql_file:
            sql_content = sql_file.read()

        # 5. Split statements and execute individually
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

        print(f"Executing {len(statements)} schema statements from database_setup.sql...")
        for idx, statement in enumerate(statements, 1):
            cursor.execute(statement)

        conn.commit()

        # 6. Verify created tables using dictionary cursor
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()

        print("\nDatabase initialization completed successfully!")
        print(f"Active database: '{db_name}'")
        print("Tables verified:")
        for table in tables:
            # dictionary=True returns e.g. {'Tables_in_digital_dukan': 'products'}
            table_name = list(table.values())[0]
            print(f"  - {table_name}")

        cursor.close()

    except mysql.connector.Error as err:
        print("\n[DATABASE ERROR] MySQL connection or execution failed:")
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print(f"  Access denied for user '{Config.DB_USER}'@'{Config.DB_HOST}'.")
            print("  Please check that DB_USER and DB_PASSWORD in your .env file are correct.")
        elif err.errno in (errorcode.CR_CONN_HOST_ERROR, 2003):
            print(f"  Could not connect to MySQL server at {Config.DB_HOST}:{Config.DB_PORT}.")
            print("  Please make sure your MySQL service (e.g. mysqld) is running and accessible.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print(f"  Database '{Config.DB_NAME}' does not exist and could not be accessed.")
        else:
            print(f"  Error [{err.errno}]: {err.msg}")
        sys.exit(1)

    except Exception as ex:
        print(f"\n[UNEXPECTED ERROR] {ex}")
        sys.exit(1)

    finally:
        if conn is not None and conn.is_connected():
            conn.close()
            print("Database connection closed cleanly.\n")


if __name__ == '__main__':
    initialize_database()
