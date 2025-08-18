import os, pandas as pd, json, requests, time
from datetime import datetime
import markdown_pdf
from app import database

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://ollama:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3')
REPORT_OUTPUT_DIR = "/app/generated_reports"

def generate_report_markdown(agency_id, report_type='single_agency'):
    conn = database.get_db_connection()
    if not conn: return "# Report Error: Could not connect to the database."

    agency_name = pd.read_sql("SELECT name FROM agencies WHERE agency_id = %s", conn, params=(agency_id,)).iloc[0]['name']

    # Placeholder for fetching rich data, as would be done in a full implementation
    gathered_data = {'agency_name': agency_name, 'report_type': report_type}

    conn.close()

    report_title = f"{agency_name} - {report_type.replace('_', ' ').title()} Report"
    prompt = f"""As a BI Analyst, write a professional report for {agency_name}.
    Start with an "Executive Summary". Then create a "Key Findings" section.
    Output must be in clean Markdown. DATA: {json.dumps(gathered_data)}"""

    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False})
        response.raise_for_status()
        narrative = response.json().get('response', 'Could not generate narrative.')
    except Exception as e:
        narrative = f"**Error:** Could not generate AI narrative. {e}"

    return f"# {report_title}\\n**Generated On:** {datetime.now().strftime('%B %d, %Y')}\\n\\n---\\n\\n{narrative}"

def convert_markdown_to_pdf(markdown_content, agency_id):
    if not os.path.exists(REPORT_OUTPUT_DIR): os.makedirs(REPORT_OUTPUT_DIR)

    conn = database.get_db_connection()
    agency_name = pd.read_sql("SELECT name FROM agencies WHERE agency_id = %s", conn, params=(agency_id,)).iloc[0]['name']
    conn.close()

    filename = f"Report_{agency_name.replace(' ', '_')}_{int(time.time())}.pdf"
    pdf_path = os.path.join(REPORT_OUTPUT_DIR, filename)

    try:
        pdf_bytes = markdown_pdf.convert(markdown_content)
        with open(pdf_path, 'wb') as f:
            f.write(pdf_bytes)
        return pdf_path
    except Exception as e:
        print(f"Error converting to PDF: {e}")
        return None
