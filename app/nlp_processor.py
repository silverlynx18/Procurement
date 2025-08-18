import os, spacy, requests, json
from app import database

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://ollama:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3')
ITS_KEYWORD_ONTOLOGY = [
    "Intelligent Transportation Systems", "ITS", "Advanced Traffic Management", "ATMS",
    "V2X", "V2V", "V2I", "Connected Vehicles", "Traffic Signal Priority", "TSP",
    "LIDAR", "ADAS", "Smart Corridor", "MaaS", "Mobility as a Service", "ANPR"
]

def load_spacy_model():
    print(f"  - NLP Engine using LLM: '{OLLAMA_MODEL}' for Tier 2 tasks.")
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        print("    - Downloading spaCy model...")
        spacy.cli.download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")
    matcher = spacy.matcher.PhraseMatcher(nlp.vocab, attr="LOWER")
    patterns = [nlp.make_doc(text) for text in ITS_KEYWORD_ONTOLOGY]
    matcher.add("ITS_KEYWORDS", patterns)
    return nlp, matcher

nlp, matcher = load_spacy_model()

def tier1_triage_text(text):
    if not isinstance(text, str): return 0, []
    doc = nlp(text)
    entities = []

    matches = matcher(doc)
    for _, start, end in matches:
        span = doc[start:end]
        entities.append({"entity_text": span.text, "entity_label": "ITS_TECHNOLOGY", "context_sentence": span.sent.text.strip()})

    for ent in doc.ents:
        if ent.label_ in ["MONEY", "DATE", "ORG"]:
            entities.append({"entity_text": ent.text, "entity_label": ent.label_, "context_sentence": ent.sent.text.strip()})

    return len(entities), entities

def process_unprocessed_documents():
    print("  - NLP Engine: Processing new documents...")
    conn = database.get_db_connection()
    if not conn: return

    with conn.cursor() as cur:
        cur.execute("""
            SELECT d.document_id, d.raw_text FROM documents d
            LEFT JOIN extracted_entities ee ON d.document_id = ee.source_id AND ee.source_type = 'document'
            WHERE d.raw_text IS NOT NULL AND ee.entity_id IS NULL
        """)
        docs_to_process = cur.fetchall()

    print(f"    - Found {len(docs_to_process)} new documents for NLP analysis.")
    for doc_id, raw_text in docs_to_process:
        _, tier1_entities = tier1_triage_text(raw_text)

        with conn.cursor() as cur_insert:
            for entity in tier1_entities:
                cur_insert.execute("INSERT INTO extracted_entities (source_id, source_type, entity_text, entity_label, context_sentence) VALUES (%s, 'document', %s, %s, %s);",
                                   (doc_id, entity['entity_text'], entity['entity_label'], entity['context_sentence']))
        conn.commit()
    conn.close()
