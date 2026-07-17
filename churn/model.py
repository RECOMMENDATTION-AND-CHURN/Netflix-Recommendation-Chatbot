"""
churn/model.py
----------------
Phase 6: Churn Prediction Model.

Trains a LightGBM classifier on data/streaming_churn_dataset.csv and saves
the trained model + exact feature column order to models/churn_model.pkl.

This module is used ONLY by dashboard.py (the provider side). The chatbot
(app.py) does not import this — churn prediction is never shown to end users,
per the project spec.

Run directly to (re)train:
    python -m churn.model
"""

import os
import logging
from typing import Dict, Optional

import joblib
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "streaming_churn_dataset.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "churn_model.pkl")

GENRE_COLUMNS = [
    "genre_Action", "genre_Comedy", "genre_Documentary", "genre_Drama",
    "genre_Horror", "genre_Romance", "genre_Sci-Fi", "genre_Thriller",
]

BASE_FEATURE_COLUMNS = [
    "login_frequency", "session_duration", "search_count",
    "recommendation_requests", "movies_clicked", "favorites_added",
    "ratings_given", "satisfaction_score", "days_since_last_login",
    "avg_rating_given",
]

FEATURE_COLUMNS = BASE_FEATURE_COLUMNS + GENRE_COLUMNS


def train() -> LGBMClassifier:
    """Trains and persists the churn model. Prints evaluation metrics."""
    df = pd.read_csv(DATA_PATH)

    X = df[FEATURE_COLUMNS]
    y = df["churn"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = LGBMClassifier(
        n_estimators=300, learning_rate=0.05, max_depth=-1, random_state=42,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]

    logger.info("Accuracy : %.4f", accuracy_score(y_test, preds))
    logger.info("ROC-AUC  : %.4f", roc_auc_score(y_test, proba))
    logger.info("\n%s", classification_report(y_test, preds))

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump({"model": model, "feature_columns": FEATURE_COLUMNS}, MODEL_PATH)
    logger.info("Saved model -> %s", MODEL_PATH)

    return model


def _load_bundle() -> dict:
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"No trained model at {MODEL_PATH}. Run `python -m churn.model` first."
        )
    return joblib.load(MODEL_PATH)


def build_feature_row(activity: Dict, preferred_genre: Optional[str] = None) -> pd.DataFrame:
    """Converts a user_activity dict into a single-row DataFrame matching training layout."""
    row = {col: activity.get(col, 0) or 0 for col in BASE_FEATURE_COLUMNS}

    genre_row = {col: 0 for col in GENRE_COLUMNS}
    genre = preferred_genre or activity.get("preferred_genre")
    if genre:
        col_name = f"genre_{genre}"
        if col_name in genre_row:
            genre_row[col_name] = 1
        # unknown genres (e.g. "Fantasy", "Animation") stay all-zero —
        # the model wasn't trained on those categories

    row.update(genre_row)
    return pd.DataFrame([row], columns=FEATURE_COLUMNS)


def predict_churn_probability(activity: Dict, preferred_genre: Optional[str] = None) -> float:
    """Returns churn probability (0.0-1.0) for one user's activity snapshot."""
    bundle = _load_bundle()
    model = bundle["model"]
    feature_columns = bundle["feature_columns"]

    X = build_feature_row(activity, preferred_genre)[feature_columns]
    return float(model.predict_proba(X)[0][1])


def risk_label(probability: float) -> str:
    if probability >= 0.7:
        return "High Risk"
    elif probability >= 0.4:
        return "Medium Risk"
    return "Low Risk"


if __name__ == "__main__":
    train()
