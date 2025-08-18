import pandas as pd
import json
import os
import requests
from app import database

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://ollama:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3')

def handle_query(query, selected_agencies_df):
    if selected_agencies_df.empty:
        return "Please make a selection on the map to query the data."

    query_lower = query.lower()

    if any(keyword in query_lower for keyword in ["rfp", "soon", "opportunity", "high probability"]):
        return answer_top_opportunities(selected_agencies_df)

    if "summarize" in query_lower:
        return answer_summary(selected_agencies_df)

    return answer_with_rag(query, selected_agencies_df)

def answer_top_opportunities(df):
    high_prob_df = df[df['prob_12_months'] > 0.5].sort_values(by='prob_12_months', ascending=False)

    if high_prob_df.empty:
        return "Based on current data, none of the selected agencies show a high probability (>50%) of releasing a relevant solicitation in the next 12 months."

    response_md = "Based on the predictive model, the following members are most likely to release relevant solicitations soon:\\n\\n"

    for _, row in high_prob_df.head(5).iterrows():
        response_md += f"- **{row['name']}** ({row['agency_type']})\\n"
        response_md += f"  - **Predicted Likelihood (12-Mo): {row['prob_12_months']:.1%}**\\n"

    return response_md

def answer_summary(df):
    count = len(df)
    high_prob_count = len(df[df['prob_12_months'] > 0.5])
    avg_prob = df['prob_12_months'].mean()
    return f"""Your current selection includes:
- **Total Agencies:** {count}
- **High-Probability Targets (>50%):** {high_prob_count}
- **Average 12-Month Likelihood:** {avg_prob:.1%}
"""

def answer_with_rag(query, df):
    prompt = f"""You are an AI assistant for a business intelligence platform. A user has selected a group of transportation agencies and has asked a question. Use ONLY the provided data (in JSON format) to formulate a concise, professional answer. If the data cannot answer the question, state that clearly.

USER QUERY:
"{query}"

AVAILABLE DATA:
{df.to_json(orient='records', indent=2)}
"""
    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        return response.json().get('response', "I was unable to process this query.")
    except Exception as e:
        return f"Error connecting to the AI model: {e}"
