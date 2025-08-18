import sys, time, random, json
import pandas as pd
from faker import Faker
from app import database

def create_enhanced_tables():
    """Creates the full database schema."""
    conn = database.get_db_connection()
    if not conn: return

    commands = (
        "DO $$ BEGIN CREATE TYPE validation_status AS ENUM ('unverified', 'correct', 'incorrect'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
        "CREATE TABLE IF NOT EXISTS agencies ( agency_id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, state VARCHAR(100), agency_type VARCHAR(100), procurement_url TEXT, planning_url TEXT, minutes_url TEXT, latitude FLOAT, longitude FLOAT );",
        "CREATE TABLE IF NOT EXISTS documents ( document_id SERIAL PRIMARY KEY, agency_id INTEGER REFERENCES agencies(agency_id), document_type VARCHAR(50), url TEXT, local_path VARCHAR(255), scraped_date TIMESTAMP, publication_date DATE, raw_text TEXT );",
        "CREATE TABLE IF NOT EXISTS extracted_entities ( entity_id SERIAL PRIMARY KEY, source_id INTEGER, source_type VARCHAR(50), entity_text TEXT, entity_label VARCHAR(100), context_sentence TEXT, validation_status validation_status NOT NULL DEFAULT 'unverified' );",
        "CREATE TABLE IF NOT EXISTS news_articles ( article_id SERIAL PRIMARY KEY, agency_id INTEGER REFERENCES agencies(agency_id) ON DELETE CASCADE, article_url TEXT UNIQUE NOT NULL, title TEXT, source_name VARCHAR(255), published_date TIMESTAMP WITH TIME ZONE, content TEXT );",
        "CREATE TABLE IF NOT EXISTS predictions ( prediction_id SERIAL PRIMARY KEY, agency_id INTEGER REFERENCES agencies(agency_id), prediction_date DATE, prob_6_months FLOAT, prob_12_months FLOAT, supporting_evidence JSONB );",
        "CREATE TABLE IF NOT EXISTS governmental_structures ( structure_id SERIAL PRIMARY KEY, name VARCHAR(255) UNIQUE NOT NULL, description TEXT, influence_weight FLOAT NOT NULL DEFAULT 0.5 );",
        "CREATE TABLE IF NOT EXISTS agency_relationships ( relationship_id SERIAL PRIMARY KEY, parent_agency_id INTEGER NOT NULL REFERENCES agencies(agency_id) ON DELETE CASCADE, child_agency_id INTEGER NOT NULL REFERENCES agencies(agency_id) ON DELETE CASCADE, structure_id INTEGER NOT NULL REFERENCES governmental_structures(structure_id) ON DELETE CASCADE, UNIQUE(parent_agency_id, child_agency_id, structure_id) );",
        "CREATE TABLE IF NOT EXISTS historical_solicitations ( solicitation_id SERIAL PRIMARY KEY, agency_id INTEGER REFERENCES agencies(agency_id), release_date DATE NOT NULL, title TEXT, url TEXT UNIQUE, keywords TEXT[] );",
        "CREATE TABLE IF NOT EXISTS backtest_results ( result_id SERIAL PRIMARY KEY, simulation_date DATE NOT NULL, agency_id INTEGER REFERENCES agencies(agency_id), predicted_prob_12m FLOAT, actual_outcome_12m BOOLEAN, time_to_event_days INTEGER, UNIQUE(simulation_date, agency_id) );",
        "CREATE TABLE IF NOT EXISTS quality_review_cases ( case_id SERIAL PRIMARY KEY, entity_id INTEGER NOT NULL REFERENCES extracted_entities(entity_id) ON DELETE CASCADE, reason_for_review TEXT, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, UNIQUE(entity_id) );",
        "CREATE TABLE IF NOT EXISTS agency_context_briefs ( agency_id INT PRIMARY KEY REFERENCES agencies(agency_id) ON DELETE CASCADE, brief_markdown TEXT, last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP );"
    )
    with conn.cursor() as cur:
        for command in commands:
            cur.execute(command)
    conn.commit()
    conn.close()
    print("  - All tables created successfully.")

def seed_agencies():
    conn = database.get_db_connection()
    if not conn: return
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM agencies")
        if cur.fetchone()[0] > 0:
            print("  - Agencies table already contains data. Skipping seed.")
            conn.close()
            return
    df = pd.read_csv('/app/data/publicsector.csv')
    df = df[['Agency Name', 'State', 'Agency Type', 'URL', 'Planning Website URL', 'Public Minutes URL', 'Latitude', 'Longitude']].copy()
    df.columns = ['name', 'state', 'agency_type', 'procurement_url', 'planning_url', 'minutes_url', 'latitude', 'longitude']
    with conn.cursor() as cur:
        for _, row in df.iterrows():
            cur.execute("INSERT INTO agencies (name, state, agency_type, procurement_url, planning_url, minutes_url, latitude, longitude) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", tuple(row))
    conn.commit()
    conn.close()
    print(f"  - Seeded {len(df)} agencies.")

def seed_structures():
    conn = database.get_db_connection()
    if not conn: return
    types = [('Member Of', 'Child is a member of parent.', 0.75), ('Component Of', 'Child is a sub-unit of parent.', 0.9), ('Overseen By', 'Parent has oversight.', 0.4), ('Funded By', 'Parent provides funding.', 0.8)]
    with conn.cursor() as cur:
        for name, desc, weight in types: cur.execute("INSERT INTO governmental_structures (name, description, influence_weight) VALUES (%s, %s, %s) ON CONFLICT (name) DO NOTHING;", (name, desc, weight))
    conn.commit()
    conn.close()
    print("  - Governmental structure types seeded.")

def initial_setup():
    print("--- Performing Initial One-Time Database Setup ---")
    time.sleep(5)
    create_enhanced_tables()
    seed_agencies()
    seed_structures()
    print("\\n--- Initial Setup Complete ---")

def generate_mock_data():
    Faker.seed(0)
    fake = Faker()
    print("--- Generating Mock Data for Dashboard Proofing ---")
    conn = database.get_db_connection()
    if not conn: return
    with conn.cursor() as cur:
        cur.execute("TRUNCATE predictions, extracted_entities, documents, news_articles RESTART IDENTITY;")
        cur.execute("SELECT agency_id FROM agencies;")
        agency_ids = [row[0] for row in cur.fetchall()]
    for agency_id in agency_ids:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO predictions (agency_id, prediction_date, prob_12_months) VALUES (%s, NOW(), %s);", (agency_id, random.uniform(0.05, 0.95)))
            cur.execute("INSERT INTO documents (agency_id, document_type, raw_text, scraped_date) VALUES (%s, 'Planning Document', %s, NOW()) RETURNING document_id;", (agency_id, fake.paragraph()))
            doc_id = cur.fetchone()[0]
            cur.execute("INSERT INTO extracted_entities (source_id, source_type, entity_text, entity_label, context_sentence) VALUES (%s, 'document', %s, 'ITS_TECHNOLOGY', %s);", (doc_id, random.choice(['V2X', 'Smart Corridor']), fake.sentence()))
    conn.commit()
    conn.close()
    print("--- Mock Data Generation Complete ---")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--setup': initial_setup()
    elif len(sys.argv) > 1 and sys.argv[1] == '--mock': generate_mock_data()
    else: print("Usage: python -m app.database_setup [--setup | --mock]")
