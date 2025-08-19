import sqlite3

DB_FILE = "local_database.db"

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        return conn
    except sqlite3.Error as e:
        print(f"DATABASE CONNECTION ERROR: {e}")
        return None
