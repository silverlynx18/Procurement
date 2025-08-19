import os
import requests
import json
from app import database

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://ollama:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3')

def generate_state_brief(state_name):
    """Generates an informative brief about a state's transportation structure."""
    conn = database.get_db_connection()
    if not conn: return "Could not connect to the database."
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name, agency_type FROM agencies WHERE state = %s ORDER BY agency_type", (state_name,))
            agencies_in_state = cur.fetchall()
    finally:
        if conn: conn.close()
    if not agencies_in_state: return f"No agency data found for {state_name}."

    agency_list_str = "\\n".join([f"- {name} ({agency_type})" for name, agency_type in agencies_in_state])
    prompt = f"""You are an expert analyst in U.S. public sector transportation governance.
Provide a concise, professional brief on the typical governmental structure for transportation projects in {state_name}.
Use this list of known agencies as context: {agency_list_str}
Explain the roles of the State DOT, MPOs, COGs, and local entities and how projects flow from planning to solicitation.
"""
    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        return response.json().get('response', 'Failed to generate brief.')
    except requests.exceptions.RequestException as e:
        return f"Error connecting to the AI model: {e}"
