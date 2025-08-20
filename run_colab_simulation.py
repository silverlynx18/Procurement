import os
import sys
import subprocess

def fix_python_path():
    """
    Adds the project's root directory to the Python path to ensure
    that modules within 'app' and 'scripts' can be imported correctly.
    """
    # The absolute path of the directory containing this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Add the parent directory (the project root) to sys.path
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        print(f"Adding project root to Python path: {project_root}")
        sys.path.insert(0, project_root)

def run_script(script_path, args=None):
    """
    Runs a Python script as a subprocess and handles errors.

    Args:
        script_path (str): The relative path to the script from the project root.
        args (list, optional): A list of command-line arguments for the script.
    """
    command = [sys.executable, script_path]
    if args:
        command.extend(args)

    print(f"\n--- Running script: {' '.join(command)} ---")

    try:
        # We use subprocess to run each script in its own environment, which is
        # cleaner and avoids potential conflicts between modules.
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        print(process.stdout)
        if process.stderr:
            print("--- Stderr ---", file=sys.stderr)
            print(process.stderr, file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Script {script_path} failed to execute.", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        print("\n--- Stdout ---", file=sys.stderr)
        print(e.stdout, file=sys.stderr)
        print("\n--- Stderr ---", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        sys.exit(1) # Exit the simulation if any step fails

def main():
    """
    Orchestrates the entire Colab/local simulation pipeline in the correct
    logical order.
    """
    print("--- Starting Colab Simulation ---")

    # Ensure the environment is set for SQLite database
    os.environ['DB_TYPE'] = 'sqlite'
    print(f"Environment set for DB_TYPE='{os.environ['DB_TYPE']}'")

    # Define the sequence of scripts to run
    # Note: We run these as subprocesses to ensure each runs in a clean state.
    scripts_to_run = [
        {"path": "app/database_setup.py"},
        {"path": "scripts/seed_houston_relationships.py"},
        {"path": "scripts/run_regional_scrape.py", "args": ["Houston"]},
        {"path": "scripts/verify_db.py"}
    ]

    for script_info in scripts_to_run:
        run_script(script_info["path"], script_info.get("args"))

    print("\n--- Colab Simulation Finished Successfully ---")


if __name__ == "__main__":
    # This script does not need the path fix itself, but it ensures that
    # the subprocesses it calls can find their modules.
    main()
