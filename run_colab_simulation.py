import os
import sys

def fix_python_path():
    """
    Adds the project's root directory to the Python path to ensure
    that modules within 'app' and 'scripts' can be imported correctly.
    """
    # In Colab, the root is typically /content/Procurement
    # We assume this script is in the root of the cloned repo.
    project_root = os.getcwd()
    if project_root not in sys.path:
        print(f"Adding project root to Python path: {project_root}")
        sys.path.insert(0, project_root)
    else:
        print("Project root is already in Python path.")

def main():
    """
    Orchestrates the entire Colab/local simulation pipeline in the correct
    logical order by importing and calling functions from other modules.
    """
    print("--- Starting Colab Simulation ---")

    # 1. SET DATABASE TYPE FIRST
    # This must be done before any local modules are imported, as they may
    # initialize database connections upon import.
    os.environ['DB_TYPE'] = 'sqlite'
    print(f"Environment set for DB_TYPE='{os.environ['DB_TYPE']}'")

    # 2. Fix python path before any local imports
    fix_python_path()

    # 3. Now that the environment and path are set, import modules
    from app import database
    from app import database_setup
    from app import scraper
    from scripts import seed_houston_relationships
    from scripts import run_regional_scrape
    from scripts import verify_db

    # 4. Run the setup and scraping pipeline in the correct order
    try:
        database_setup.initial_setup(database)
        seed_houston_relationships.seed_relationships(database)
        run_regional_scrape.run_scrape(database, scraper, "Houston")

        # 5. Verify the results
        print("\n--- Verifying Final Database State ---")
        verify_db.verify()

        print("\n--- Colab Simulation Finished Successfully ---")

    except Exception as e:
        print(f"\n--- AN ERROR OCCURRED ---")
        print(f"The simulation failed with the following error: {e}")
        print("Please review the logs above to diagnose the issue.")
        # Exit with a non-zero code to indicate failure
        sys.exit(1)


if __name__ == "__main__":
    main()
