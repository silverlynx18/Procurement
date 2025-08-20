import sys
import time
import random
import json
import pandas as pd
from faker import Faker

# This script is now designed to be imported as a module.
# The functions are called by the master simulation script.

# To prevent circular imports, we pass the database module as an argument
# instead of importing it at the top level.

def create_enhanced_tables(db_module):
    """Creates the full database schema for the configured DB_TYPE."""
    conn = db_module.get_db_connection()
    if not conn: return

    db_type = db_module.get_db_type()
    cur = conn.cursor()

    # The schema definitions are now fully agnostic.
    if db_type == 'postgres':
        commands = [
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
        ]
    else: # SQLite
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
    print(f"  - All tables created successfully for {db_type}.")

def seed_agencies(db_module):
    conn = db_module.get_db_connection()
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

    p_style = db_module.get_param_style()
    sql = f"INSERT INTO agencies (name, state, agency_type, procurement_url, planning_url, minutes_url, latitude, longitude) VALUES ({p_style}, {p_style}, {p_style}, {p_style}, {p_style}, {p_style}, {p_style}, {p_style})"

    for _, row in df.iterrows():
        cur.execute(sql, tuple(row))

    conn.commit()
    conn.close()
    print(f"  - Seeded {len(df)} agencies.")

def seed_structures(db_module):
    conn = db_module.get_db_connection()
    if not conn: return
    cur = conn.cursor()

    types = [('Member Of', 'Child is a member of parent.', 0.75), ('Component Of', 'Child is a sub-unit of parent.', 0.9), ('Overseen By', 'Parent has oversight.', 0.4), ('Funded By', 'Parent provides funding.', 0.8)]

    p_style = db_module.get_param_style()
    on_conflict = "ON CONFLICT (name) DO NOTHING" if db_module.get_db_type() == 'postgres' else "OR IGNORE"
    sql = f"INSERT {on_conflict} INTO governmental_structures (name, description, influence_weight) VALUES ({p_style}, {p_style}, {p_style})"

    for name, desc, weight in types:
        cur.execute(sql, (name, desc, weight))

    conn.commit()
    conn.close()
    print("  - Governmental structure types seeded.")

def initial_setup(db_module):
    db_type = db_module.get_db_type()
    print(f"--- Performing Initial One-Time Database Setup ({db_type}) ---")
    create_enhanced_tables(db_module)
    seed_agencies(db_module)
    seed_structures(db_module)
    print(f"--- Initial {db_type.capitalize()} Setup Complete ---")
