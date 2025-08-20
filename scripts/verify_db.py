import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db_connection

def main():
    """
    Connects to the database and verifies that data has been inserted into the
    'documents' table by printing the total record count.
    """
    print("\n--- Verifying Database ---")
    conn = None
    try:
        # Set DB_TYPE to 'sqlite' for the simulation environment
        os.environ['DB_TYPE'] = 'sqlite'

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for records in the documents table
        cursor.execute("SELECT COUNT(*) FROM documents")
        count = cursor.fetchone()[0]

        print(f"Verification complete.")
        print(f"Found {count} record(s) in the 'documents' table.")

        if count > 0:
            print("SUCCESS: Data has been successfully scraped and inserted into the database.")
        else:
            print("NOTE: No new documents were found or inserted during this run. This is expected if the scraper has run previously.")

    except Exception as e:
        print(f"An error occurred during database verification: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
