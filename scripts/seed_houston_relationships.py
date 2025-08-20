import sys
import os

# This script is now designed to be imported as a module.
# The functions are called by the master simulation script.

def seed_relationships(db_module):
    """
    Seeds the agency_relationships table for the Houston, TX proof-of-concept.
    This script is database-agnostic.

    Args:
        db_module: The database module (app.database) passed in to avoid
                   circular imports.
    """
    print("--- Seeding Houston-area agency relationships ---")
    conn = db_module.get_db_connection()
    if not conn:
        print("CRITICAL: Could not connect to the database.")
        return

    try:
        cur = conn.cursor()
        p_style = db_module.get_param_style()

        # 1. Get the agency IDs for the relevant agencies
        agency_names = {
            'parent': 'Houston-Galveston Area Council',
            'children': ['METRO (Houston)', 'Port Houston'],
            'related': 'TxDOT PEPS'
        }

        agency_ids = {}
        all_names = [agency_names['parent']] + agency_names['children'] + [agency_names['related']]
        for name in all_names:
            cur.execute(f"SELECT agency_id FROM agencies WHERE name = {p_style}", (name,))
            result = cur.fetchone()
            if result:
                agency_ids[name] = result[0]
            else:
                print(f"  - WARNING: Could not find agency_id for '{name}'")

        if agency_names['parent'] not in agency_ids:
            print("  - CRITICAL: Could not find parent agency H-GAC. Aborting.")
            return

        parent_id = agency_ids[agency_names['parent']]

        # 2. Get the structure_id for the "Component Of" relationship
        cur.execute(f"SELECT structure_id FROM governmental_structures WHERE name = {p_style}", ('Component Of',))
        structure_result = cur.fetchone()
        if not structure_result:
            print("  - CRITICAL: Could not find 'Component Of' relationship type. Aborting.")
            return
        component_of_id = structure_result[0]

        # 3. Insert the relationships
        relationships_to_add = [agency_ids.get(name) for name in agency_names['children']]

        # Define the INSERT statement with ON CONFLICT handling
        on_conflict = "ON CONFLICT(parent_agency_id, child_agency_id, structure_id) DO NOTHING" if db_module.get_db_type() == 'postgres' else "OR IGNORE"
        sql = f"INSERT {on_conflict} INTO agency_relationships (parent_agency_id, child_agency_id, structure_id) VALUES ({p_style}, {p_style}, {p_style})"

        for child_id in relationships_to_add:
            if child_id:
                print(f"  - Linking child agency {child_id} to parent {parent_id}")
                try:
                    cur.execute(sql, (parent_id, child_id, component_of_id))
                except Exception as e:
                    # This broad exception is for SQLite versions that don't support ON CONFLICT
                    if "UNIQUE constraint failed" in str(e):
                         print(f"    - Relationship for child {child_id} already exists. Skipping.")
                    else:
                        raise e

        conn.commit()
        print("--- Houston-area relationships seeded successfully. ---")

    finally:
        if conn:
            conn.close()
