import pandas as pd
import random
from datetime import datetime
from app import database

def run_guardian_agent():
    """Main orchestration function for all agentic tasks."""
    print("\\n--- [Guardian Agent] Starting Integrity and Learning Cycle ---")
    agent_create_feedback_loop()
    agent_detect_data_anomalies()
    print("--- [Guardian Agent] Cycle Complete ---")

def agent_create_feedback_loop():
    """Takes high-confidence predictions and actively seeks to confirm them."""
    print("  - Agent Task: Running Feedback Loop Creator...")
    conn = database.get_db_connection()
    if not conn: return

    try:
        query = """
        SELECT p.agency_id, a.name, a.procurement_url FROM predictions p
        JOIN agencies a ON p.agency_id = a.agency_id
        WHERE p.prob_12_months > 0.75 AND NOT EXISTS (
            SELECT 1 FROM historical_solicitations hs
            WHERE hs.agency_id = p.agency_id AND hs.release_date > (NOW() - INTERVAL '60 days')
        ) ORDER BY p.prob_12_months DESC LIMIT 5;
        """
        df = pd.read_sql_query(query, conn)

        if df.empty:
            print("    - No new, high-probability targets to check.")
            return

        for _, row in df.iterrows():
            # In a real system, a targeted scraper for solicitations would run here.
            # We simulate finding a relevant RFP.
            print(f"    - Actively checking for solicitations from: {row['name']}")
            if random.random() < 0.2: # Simulate a 20% success rate
                print(f"      >> SUCCESS! Found new solicitation. Adding to ground truth.")
                with conn.cursor() as cur:
                    sol = {'title': 'Simulated ITS Smart Corridor RFP', 'release_date': datetime.now().date(), 'url': f"http://fake.gov/{random.randint(1000,9999)}"}
                    cur.execute(
                        "INSERT INTO historical_solicitations (agency_id, release_date, title, url) VALUES (%s, %s, %s, %s) ON CONFLICT(url) DO NOTHING;",
                        (row['agency_id'], sol['release_date'], sol['title'], sol['url'])
                    )
                conn.commit()
    finally:
        if conn: conn.close()

def agent_detect_data_anomalies():
    """Runs integrity checks on the database."""
    print("  - Agent Task: Detecting Data Anomalies...")
    conn = database.get_db_connection()
    if not conn: return
    try:
        query = "SELECT document_id FROM documents WHERE (raw_text IS NULL OR LENGTH(raw_text) < 100) AND scraped_date > (NOW() - INTERVAL '7 days');"
        df_failed = pd.read_sql_query(query, conn)
        if not df_failed.empty:
            print(f"    - ALERT: Found {len(df_failed)} documents scraped in the last week with little or no text.")
    finally:
        if conn: conn.close()
