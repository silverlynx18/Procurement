import os
import sqlite3
import psycopg2

# Determine the database type from environment variables
DB_TYPE = os.environ.get('DB_TYPE', 'postgres').lower()
SQLITE_DB_FILE = "local_database.db"

def get_db_connection():
    """
    Establishes a connection to the appropriate database (PostgreSQL or SQLite)
    based on the DB_TYPE environment variable.
    """
    if DB_TYPE == 'sqlite':
        try:
            conn = sqlite3.connect(SQLITE_DB_FILE)
            return conn
        except sqlite3.Error as e:
            print(f"SQLITE DATABASE CONNECTION ERROR: {e}")
            return None
    elif DB_TYPE == 'postgres':
        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            return conn
        except psycopg2.OperationalError as e:
            print(f"POSTGRES DATABASE CONNECTION ERROR: {e}")
            return None
    else:
        raise ValueError(f"Unsupported DB_TYPE: {DB_TYPE}. Must be 'postgres' or 'sqlite'.")

def get_db_type():
    """Returns the current database type."""
    return DB_TYPE

def get_param_style():
    """Returns the parameter style placeholder for the current DB type."""
    return '?' if DB_TYPE == 'sqlite' else '%s'

def get_on_conflict_clause():
    """Returns the appropriate ON CONFLICT clause for the current DB type."""
    return 'ON CONFLICT DO NOTHING' if DB_TYPE == 'postgres' else 'OR IGNORE'
