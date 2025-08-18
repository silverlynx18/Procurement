import pandas as pd
import xgboost as xgb
import os
from datetime import datetime
from app import database

MODEL_PATH = '/app/app/xgb_model.json'

def load_model_for_prediction():
    if not os.path.exists(MODEL_PATH):
        print("    - PREDICTION ERROR: Model file 'xgb_model.json' not found. Please run train.py first.")
        return None
    model = xgb.XGBClassifier()
    model.load_model(MODEL_PATH)
    return model

def engineer_features(as_of_date=None):
    conn = database.get_db_connection()
    if not conn: return pd.DataFrame()
    date_filter = f"AND d.publication_date < '{as_of_date}'" if as_of_date else ""

    try:
        query = f"""
        SELECT
            d.agency_id,
            COUNT(CASE WHEN d.document_type = 'Planning Document' AND e.entity_label = 'ITS_TECHNOLOGY' THEN 1 END) AS planning_doc_its_mentions,
            COUNT(CASE WHEN d.document_type = 'Planning Document' AND e.entity_label = 'MONEY' THEN 1 END) AS planning_doc_budget_mentions,
            COUNT(CASE WHEN d.document_type = 'ITS Architecture' AND e.entity_label = 'ITS_TECHNOLOGY' THEN 1 END) AS its_arch_its_mentions
        FROM documents d JOIN extracted_entities e ON d.document_id = e.source_id
        WHERE e.validation_status = 'correct' {date_filter}
        GROUP BY d.agency_id;
        """
        base_features_df = pd.read_sql_query(query, conn, index_col='agency_id')

        all_agencies_df = pd.read_sql("SELECT agency_id, name FROM agencies", conn, index_col='agency_id')
        final_df = all_agencies_df.join(base_features_df).fillna(0)

        return final_df.reset_index()
    finally:
        if conn: conn.close()

def generate_predictions():
    print("  - Forecasting Model: Generating new predictions...")
    model = load_model_for_prediction()
    if not model: return

    features_df = engineer_features()
    if features_df.empty:
        print("    - No feature data available to generate predictions.")
        return

    feature_names = [col for col in features_df.columns if col.endswith('_mentions')]
    # Ensure all model features are present, even if all zero
    for f in model.get_booster().feature_names:
        if f not in feature_names:
            features_df[f] = 0
    X = features_df[model.get_booster().feature_names]

    probabilities = model.predict_proba(X)[:, 1]
    features_df['prob_12_months'] = probabilities

    conn = database.get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE predictions RESTART IDENTITY;")
            for _, row in features_df.iterrows():
                cur.execute("INSERT INTO predictions (agency_id, prediction_date, prob_12_months) VALUES (%s, %s, %s)",
                            (row['agency_id'], datetime.now().date(), row['prob_12_months']))
            conn.commit()
            print(f"    - Successfully saved {len(features_df)} new predictions.")
    finally:
        if conn: conn.close()
