import sys
import os
# Add the parent directory to the path to allow imports from `app`
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import database

def seed_relationships():
    """
    Seeds the agency_relationships table for the Houston, TX proof-of-concept (SQLite compatible).
    """
    print("--- Seeding Houston-area agency relationships ---")
    conn = database.get_db_connection()
    if not conn:
        print("CRITICAL: Could not connect to the database.")
        return

    try:
        cur = conn.cursor()

        # 1. Get the agency IDs for the relevant agencies
        agency_names = {
            'parent': 'Houston-Galveston Area Council',
            'children': [
                'METRO (Houston)',
                'Port Houston'
            ],
            'related': 'TxDOT PEPS'
        }

        agency_ids = {}
        all_names = [agency_names['parent']] + agency_names['children'] + [agency_names['related']]
        for name in all_names:
            cur.execute("SELECT agency_id FROM agencies WHERE name = ?", (name,))
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
        cur.execute("SELECT structure_id FROM governmental_structures WHERE name = 'Component Of'")
        structure_result = cur.fetchone()
        if not structure_result:
            print("  - CRITICAL: Could not find 'Component Of' relationship type. Aborting.")
            return
        component_of_id = structure_result[0]

        # 3. Insert the relationships
        relationships_to_add = [
            agency_ids.get('METRO (Houston)'),
            agency_ids.get('Port Houston')
        ]

        for child_id in relationships_to_add:
            if child_id:
                print(f"  - Linking child agency {child_id} to parent {parent_id}")
                try:
                    cur.execute(
                        "INSERT INTO agency_relationships (parent_agency_id, child_agency_id, structure_id) VALUES (?, ?, ?)",
                        (parent_id, child_id, component_of_id)
                    )
                except conn.IntegrityError:
                    print(f"    - Relationship for child {child_id} already exists. Skipping.")

        conn.commit()
        print("--- Houston-area relationships seeded successfully. ---")

    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    seed_relationships()
