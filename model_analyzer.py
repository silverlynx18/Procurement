import xgboost as xgb
import shap
import pandas as pd
import matplotlib.pyplot as plt

def analyze_feature_importance():
    print("--- Analyzing Model Feature Importance ---")
    model = xgb.XGBClassifier()
    model.load_model('app/xgb_model.json')
    try:
        df = pd.read_csv('training_data.csv', index_col=0)
    except FileNotFoundError:
        print("CRITICAL ERROR: 'training_data.csv' not found. Please run 'train.py' first.")
        return

    features = [col for col in df.columns if '_mentions' in col or '_count' in col]
    X = df[features]

    print("  - Calculating and plotting SHAP values...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    plt.figure()
    shap.summary_plot(shap_values, X, plot_type="bar", show=False)
    plt.title("Overall Feature Importance (SHAP)")
    plt.tight_layout()
    plt.savefig('feature_importance_shap.png')
    plt.close()
    print("  - >> SHAP plot saved to feature_importance_shap.png")

if __name__ == '__main__':
    analyze_feature_importance()
