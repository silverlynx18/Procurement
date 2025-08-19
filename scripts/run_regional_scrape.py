import sys
import os
import argparse

# Add the parent directory to the path to allow imports from `app`
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import database
from app import scraper

def get_regional_agency_ids(region_name):
    """
    Finds all agency IDs associated with a given region name (SQLite compatible).
    This includes the region's parent COG/MPO and all its children.
    It also looks for the state's DOT.
    """
    print(f"--- Finding all agencies for region: {region_name} ---")
    conn = database.get_db_connection()
    if not conn: return []

    agency_ids = set()

    try:
        cur = conn.cursor()

        # 1. Find the parent agency (e.g., the COG/MPO for the region)
        cur.execute("SELECT agency_id, state FROM agencies WHERE name LIKE ?", (f"%{region_name}%",))
        parent_result = cur.fetchone()

        if not parent_result:
            print(f"  - No parent agency found for region '{region_name}'.")
            return []

        parent_id, state = parent_result
        print(f"  - Found parent agency '{region_name}' with ID {parent_id} in state {state}.")
        agency_ids.add(parent_id)

        # 2. Find all children of the parent agency
        cur.execute("SELECT child_agency_id FROM agency_relationships WHERE parent_agency_id = ?", (parent_id,))
        child_results = cur.fetchall()
        for row in child_results:
            agency_ids.add(row[0])
        print(f"  - Found {len(child_results)} child agencies.")

        # 3. Find the state DOT for that region
        cur.execute("SELECT agency_id FROM agencies WHERE state = ? AND agency_type = 'State DOT'", (state,))
        dot_result = cur.fetchone()
        if dot_result:
            agency_ids.add(dot_result[0])
            print(f"  - Found state DOT with ID {dot_result[0]}.")

    finally:
        if conn:
            conn.close()

    final_ids = list(agency_ids)
    print(f"--- Total agencies to scrape for {region_name}: {len(final_ids)} ---")
    return final_ids

def run_scrape_for_region(region_name):
    """
    Orchestrates the scraping process for a given region.
    """
    print(f"--- Starting regional scrape for '{region_name}' ---")

    target_ids = get_regional_agency_ids(region_name)

    if not target_ids:
        print("No agencies found for the specified region. Exiting.")
        return

    # Now, call the refactored scraping functions with the target list
    scraper.scrape_all_agencies(target_agency_ids=target_ids)
    scraper.scrape_news_for_agencies(target_agency_ids=target_ids)

    print(f"--- Regional scrape for '{region_name}' complete. ---")

def main():
    """
    Parses command-line arguments and runs the regional scrape.
    """
    parser = argparse.ArgumentParser(description="Run a targeted regional scrape.")
    parser.add_argument("region_name", type=str, help="The name of the region to scrape (e.g., 'Houston').")
    args = parser.parse_args()
    run_scrape_for_region(args.region_name)

if __name__ == '__main__':
    main()
