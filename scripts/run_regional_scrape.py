import sys
import os

# This script is now designed to be imported as a module.
# The functions are called by the master simulation script.

def get_regional_agency_ids(db_module, region_name):
    """
    Finds all agency IDs associated with a given region name.
    This includes the region's parent COG/MPO, all its children, and the state's DOT.

    Args:
        db_module: The database module (app.database).
        region_name (str): The name of the region to find agencies for.
    """
    print(f"--- Finding all agencies for region: {region_name} ---")
    conn = db_module.get_db_connection()
    if not conn: return []

    agency_ids = set()
    p_style = db_module.get_param_style()

    try:
        cur = conn.cursor()

        # 1. Find the parent agency (e.g., the COG/MPO for the region)
        cur.execute(f"SELECT agency_id, state FROM agencies WHERE name LIKE {p_style}", (f"%{region_name}%",))
        parent_result = cur.fetchone()

        if not parent_result:
            print(f"  - No parent agency found for region '{region_name}'.")
            return []

        parent_id, state = parent_result
        print(f"  - Found parent agency '{region_name}' with ID {parent_id} in state {state}.")
        agency_ids.add(parent_id)

        # 2. Find all children of the parent agency
        cur.execute(f"SELECT child_agency_id FROM agency_relationships WHERE parent_agency_id = {p_style}", (parent_id,))
        child_results = cur.fetchall()
        for row in child_results:
            agency_ids.add(row[0])
        print(f"  - Found {len(child_results)} child agencies.")

        # 3. Find the state DOT for that region
        cur.execute(f"SELECT agency_id FROM agencies WHERE state = {p_style} AND agency_type = 'State DOT'", (state,))
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

def run_scrape(db_module, scraper_module, region_name, use_ai_finder=False):
    """
    Orchestrates the scraping process for a given region.

    Args:
        db_module: The app.database module.
        scraper_module: The app.scraper module.
        region_name (str): The name of the region to scrape.
        use_ai_finder (bool): Whether to use the AI link finder.
    """
    print(f"\n--- Starting Regional Scrape for '{region_name}' ---")
    if use_ai_finder:
        print("--- AI-powered link finding is ENABLED ---")

    target_ids = get_regional_agency_ids(db_module, region_name)

    if not target_ids:
        print("No agencies found for the specified region. Exiting.")
        return

    # Now, call the scraping functions with the target list
    scraper_module.scrape_all_agencies(target_agency_ids=target_ids, use_ai_finder=use_ai_finder)
    scraper_module.scrape_news_for_agencies(target_agency_ids=target_ids)

    print(f"--- Regional scrape for '{region_name}' complete. ---")
