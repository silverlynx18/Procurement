import pandas as pd
import xgboost as xgb
from datetime import timedelta
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from app import database, prediction_model

PREDICTION_WINDOW_DAYS = 365

def create_training_dataset():
    print("--- Creating Training Dataset from Historical Data ---")
    conn = database.get_db_connection()
    if not conn: exit("DB Connection Failed.")

    solicitations_df = pd.read_sql("SELECT agency_id, release_date FROM historical_solicitations", conn)
    solicitations_df['release_date'] = pd.to_datetime(solicitations_df['release_date'])

    # We create a snapshot for every agency at the start of each quarter
    time_snapshots = pd.to_datetime(pd.date_range(start='2011-01-01', end='2023-01-01', freq='6M'))
    training_examples = []

    for snapshot_date in time_snapshots:
        print(f"  - Generating features for snapshot: {snapshot_date.date()}")
        features_snapshot = prediction_model.engineer_features(as_of_date=str(snapshot_date.date()))
        if features_snapshot.empty: continue
        features_snapshot['snapshot_date'] = snapshot_date

        def get_outcome(row):
            future_releases = solicitations_df[
                (solicitations_df['agency_id'] == row['agency_id']) &
                (solicitations_df['release_date'] > row['snapshot_date']) &
                (solicitations_df['release_date'] <= row['snapshot_date'] + timedelta(days=PREDICTION_WINDOW_DAYS))
            ]
            return 1 if not future_releases.empty else 0

        features_snapshot['outcome'] = features_snapshot.apply(get_outcome, axis=1)
        training_examples.append(features_snapshot)

    conn.close()
    if not training_examples:
        print("Error: No training examples generated. Ensure historical_solicitations table is populated.")
        return pd.DataFrame()

    full_training_df = pd.concat(training_examples, ignore_index=True)
    full_training_df.to_csv('training_data.csv')
    return full_training_df

def train_and_evaluate():
    df = create_training_dataset()
    if df.empty: return

    features = [col for col in df.columns if '_mentions' in col or '_count' in col]
    X = df[features]
    y = df['outcome']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    pos_weight = (y_train == 0).sum() / (y_train == 1).sum() if (y_train == 1).sum() > 0 else 1

    print("\\n--- Training Final Predictive Model ---")
    model = xgb.XGBClassifier(use_label_encoder=False, eval_metric='logloss', scale_pos_weight=pos_weight)
    model.fit(X_train, y_train)
    model.save_model('app/xgb_model.json')
    print("  - Model artifact saved to app/xgb_model.json")

    print("\\n--- Model Performance Evaluation ---")
    preds = model.predict(X_test)
    probs = model.predict_proba(X_test)[:, 1]
    print(f"  - Accuracy: {accuracy_score(y_test, preds):.2f}, Precision: {precision_score(y_test, preds):.2f}, Recall: {recall_score(y_test, preds):.2f}, AUC-ROC: {roc_auc_score(y_test, probs):.2f}")

if __name__ == '__main__':
    train_and_evaluate()
