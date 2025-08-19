import sys
import time
import random
import json
import pandas as pd
from faker import Faker
from app import database

def create_enhanced_tables():
    """Creates the full database schema for SQLite."""
    conn = database.get_db_connection()
    if not conn: return

    cur = conn.cursor()

    commands = [
        "CREATE TABLE IF NOT EXISTS agencies ( agency_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, state TEXT, agency_type TEXT, procurement_url TEXT, planning_url TEXT, minutes_url TEXT, latitude REAL, longitude REAL );",
        "CREATE TABLE IF NOT EXISTS documents ( document_id INTEGER PRIMARY KEY AUTOINCREMENT, agency_id INTEGER, raw_text TEXT, document_type TEXT, url TEXT, local_path TEXT, scraped_date TEXT, publication_date TEXT, FOREIGN KEY(agency_id) REFERENCES agencies(agency_id) );",
        "CREATE TABLE IF NOT EXISTS extracted_entities ( entity_id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER, source_type TEXT, entity_text TEXT, entity_label TEXT, context_sentence TEXT, validation_status TEXT NOT NULL DEFAULT 'unverified' );",
        "CREATE TABLE IF NOT EXISTS news_articles ( article_id INTEGER PRIMARY KEY AUTOINCREMENT, agency_id INTEGER, article_url TEXT UNIQUE NOT NULL, title TEXT, source_name TEXT, published_date TEXT, content TEXT, FOREIGN KEY(agency_id) REFERENCES agencies(agency_id) ON DELETE CASCADE );",
        "CREATE TABLE IF NOT EXISTS predictions ( prediction_id INTEGER PRIMARY KEY AUTOINCREMENT, agency_id INTEGER, prediction_date TEXT, prob_6_months REAL, prob_12_months REAL, supporting_evidence TEXT, FOREIGN KEY(agency_id) REFERENCES agencies(agency_id) );",
        "CREATE TABLE IF NOT EXISTS governmental_structures ( structure_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, influence_weight REAL NOT NULL DEFAULT 0.5 );",
        "CREATE TABLE IF NOT EXISTS agency_relationships ( relationship_id INTEGER PRIMARY KEY AUTOINCREMENT, parent_agency_id INTEGER NOT NULL, child_agency_id INTEGER NOT NULL, structure_id INTEGER NOT NULL, FOREIGN KEY(parent_agency_id) REFERENCES agencies(agency_id) ON DELETE CASCADE, FOREIGN KEY(child_agency_id) REFERENCES agencies(agency_id) ON DELETE CASCADE, FOREIGN KEY(structure_id) REFERENCES governmental_structures(structure_id) ON DELETE CASCADE, UNIQUE(parent_agency_id, child_agency_id, structure_id) );",
        "CREATE TABLE IF NOT EXISTS historical_solicitations ( solicitation_id INTEGER PRIMARY KEY AUTOINCREMENT, agency_id INTEGER, release_date TEXT NOT NULL, title TEXT, url TEXT UNIQUE, keywords TEXT, FOREIGN KEY(agency_id) REFERENCES agencies(agency_id) );",
        "CREATE TABLE IF NOT EXISTS backtest_results ( result_id INTEGER PRIMARY KEY AUTOINCREMENT, simulation_date TEXT NOT NULL, agency_id INTEGER, predicted_prob_12m REAL, actual_outcome_12m INTEGER, time_to_event_days INTEGER, UNIQUE(simulation_date, agency_id), FOREIGN KEY(agency_id) REFERENCES agencies(agency_id) );",
        "CREATE TABLE IF NOT EXISTS quality_review_cases ( case_id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id INTEGER NOT NULL, reason_for_review TEXT, created_at TEXT DEFAULT (datetime('now')), UNIQUE(entity_id), FOREIGN KEY(entity_id) REFERENCES extracted_entities(entity_id) ON DELETE CASCADE );",
        "CREATE TABLE IF NOT EXISTS agency_context_briefs ( agency_id INTEGER PRIMARY KEY, brief_markdown TEXT, last_updated_at TEXT DEFAULT (datetime('now')), FOREIGN KEY(agency_id) REFERENCES agencies(agency_id) ON DELETE CASCADE );"
    ]

    for command in commands:
        cur.execute(command)

    conn.commit()
    conn.close()
    print("  - All tables created successfully for SQLite.")

def seed_agencies():
    conn = database.get_db_connection()
    if not conn: return
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM agencies")
    if cur.fetchone()[0] > 0:
        print("  - Agencies table already contains data. Skipping seed.")
        conn.close()
        return

    try:
        df = pd.read_csv('data/publicsector.csv')
    except FileNotFoundError:
        print("  - CRITICAL: data/publicsector.csv not found. Cannot seed agencies.")
        conn.close()
        return

    df = df[['Agency Name', 'State', 'Agency Type', 'URL', 'Planning Website URL', 'Public Minutes URL', 'Latitude', 'Longitude']].copy()
    df.columns = ['name', 'state', 'agency_type', 'procurement_url', 'planning_url', 'minutes_url', 'latitude', 'longitude']

    for _, row in df.iterrows():
        cur.execute("INSERT INTO agencies (name, state, agency_type, procurement_url, planning_url, minutes_url, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", tuple(row))

    conn.commit()
    conn.close()
    print(f"  - Seeded {len(df)} agencies.")

def seed_structures():
    conn = database.get_db_connection()
    if not conn: return
    cur = conn.cursor()

    types = [('Member Of', 'Child is a member of parent.', 0.75), ('Component Of', 'Child is a sub-unit of parent.', 0.9), ('Overseen By', 'Parent has oversight.', 0.4), ('Funded By', 'Parent provides funding.', 0.8)]

    for name, desc, weight in types:
        try:
            cur.execute("INSERT INTO governmental_structures (name, description, influence_weight) VALUES (?, ?, ?)", (name, desc, weight))
        except conn.IntegrityError:
            # This will happen if the name is not unique, which is fine for seeding.
            pass

    conn.commit()
    conn.close()
    print("  - Governmental structure types seeded.")

def initial_setup():
    print("--- Performing Initial One-Time Database Setup (SQLite) ---")
    create_enhanced_tables()
    seed_agencies()
    seed_structures()
    print("\\n--- Initial SQLite Setup Complete ---")

def generate_mock_data():
    Faker.seed(0)
    fake = Faker()
    print("--- Generating Mock Data for Dashboard Proofing (SQLite) ---")
    conn = database.get_db_connection()
    if not conn: return
    cur = conn.cursor()

    # Use DELETE instead of TRUNCATE for SQLite
    cur.execute("DELETE FROM predictions;")
    cur.execute("DELETE FROM extracted_entities;")
    cur.execute("DELETE FROM documents;")
    cur.execute("DELETE FROM news_articles;")

    cur.execute("SELECT agency_id FROM agencies;")
    agency_ids = [row[0] for row in cur.fetchall()]

    for agency_id in agency_ids:
        cur.execute("INSERT INTO predictions (agency_id, prediction_date, prob_12_months) VALUES (?, date('now'), ?);", (agency_id, random.uniform(0.05, 0.95)))
        cur.execute("INSERT INTO documents (agency_id, document_type, raw_text, scraped_date) VALUES (?, 'Planning Document', ?, datetime('now'))", (agency_id, fake.paragraph()))
        doc_id = cur.lastrowid
        cur.execute("INSERT INTO extracted_entities (source_id, source_type, entity_text, entity_label, context_sentence) VALUES (?, 'document', ?, 'ITS_TECHNOLOGY', ?);", (doc_id, random.choice(['V2X', 'Smart Corridor']), fake.sentence()))

    conn.commit()
    conn.close()
    print("--- Mock Data Generation Complete ---")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--setup': initial_setup()
    elif len(sys.argv) > 1 and sys.argv[1] == '--mock': generate_mock_data()
    else: print("Usage: python -m app.database_setup [--setup | --mock]")
