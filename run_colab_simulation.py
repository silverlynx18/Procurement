import sys
import os

# Add the project root to the path to allow imports
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app import database_setup
from scripts import seed_houston_relationships
from scripts import run_regional_scrape
from scripts import verify_db

def run_full_simulation():
    """
    Orchestrates the entire proof-of-concept simulation for the Houston region.
    This script is designed to be run in a prepared Google Colab environment.
    """
    print("=================================================")
    print("=== STARTING HOUSTON PROOF-OF-CONCEPT SCRAPE  ===")
    print("=================================================\n")

    # Step 1: Create and seed the initial database
    print("\n--- STEP 1: Setting up SQLite Database ---\n")
    database_setup.initial_setup()

    # Step 2: Seed the agency relationships for the Houston region
    print("\n--- STEP 2: Seeding Houston Agency Relationships ---\n")
    seed_houston_relationships.seed_relationships()

    # Step 3: Run the targeted scrape for the Houston region
    print("\n--- STEP 3: Running Targeted Scrape for Houston Region ---\n")
    run_regional_scrape.run_scrape_for_region("Houston")

    # Step 4: Verify the data in the database
    print("\n--- STEP 4: Verifying Scraped Data ---\n")
    verify_db.verify_data()

    print("\n=================================================")
    print("=== SIMULATION COMPLETE                       ===")
    print("=================================================\n")

if __name__ == '__main__':
    run_full_simulation()
