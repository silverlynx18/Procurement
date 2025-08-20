import os
import sys

# Add the project root to the Python path to allow imports from 'app'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.database import get_db_connection

def verify():
    """
    Connects to the database and prints the record counts of key tables
    to verify the simulation's data ingestion steps.
    """
    print("\n--- Verifying Database State ---")
    conn = get_db_connection()
    if not conn:
        print("Could not connect to the database for verification.")
        return

    try:
        cur = conn.cursor()

        tables_to_check = [
            "agencies",
            "governmental_structures",
            "agency_relationships",
            "documents",
            "news_articles",
            "extracted_entities",
            "predictions"
        ]

        print("Checking record counts in all relevant tables...")
        for table in tables_to_check:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"  - Found {count} records in '{table}' table.")
            except Exception as e:
                print(f"  - Could not query table '{table}'. It might not exist. Error: {e}")

    finally:
        if conn:
            conn.close()
        print("--- Verification Complete ---")


if __name__ == "__main__":
    verify()
