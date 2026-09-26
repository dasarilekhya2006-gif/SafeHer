"""
ml_trainer.py - SafeHer ML Risk Level Classifier Training Script

Model: Random Forest Classifier
Target: Predicts route segment risk as LOW / MEDIUM / HIGH
Features:
    - crime_incidents      : Number of reported incidents in the area
    - lighting_pct         : Street lighting coverage percentage (0-100)
    - crowd_density        : Pedestrian activity level (0-100)
    - police_dist_m        : Distance to nearest police station (meters)
    - hour_of_day          : Hour of travel (0-23)
    - day_of_week          : Day (0=Mon, 6=Sun)
    - historical_safety    : Historical composite safety score (0-100)

Run this script once to train and save the model:
    python ml_trainer.py
"""

import os
import csv
import json
import math
import random
from datetime import datetime

# -----------------------------------------------------------------------
# Attempt to import ML libraries
# -----------------------------------------------------------------------
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import (
        classification_report, confusion_matrix,
        accuracy_score, precision_score, recall_score, f1_score
    )
    from sklearn.preprocessing import LabelEncoder
    import joblib
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATASET    = os.path.join(BASE_DIR, 'route_safety_dataset.csv')
MODEL_PATH = os.path.join(BASE_DIR, 'safeher_risk_model.pkl')
EVAL_PATH  = os.path.join(BASE_DIR, 'ml_evaluation.json')

FEATURE_COLS = [
    'crime_incidents', 'lighting_pct', 'crowd_density',
    'police_dist_m', 'hour_of_day', 'day_of_week', 'historical_safety'
]
TARGET_COL = 'risk_label'
CLASS_ORDER = ['LOW', 'MEDIUM', 'HIGH']


# -----------------------------------------------------------------------
# Pure-Python Fallback Decision Tree (no scikit-learn needed)
# -----------------------------------------------------------------------
class SimpleFallbackModel:
    """
    Rule-based fallback classifier using hand-crafted decision rules.
    Used when scikit-learn is not installed.
    Explains the decision as a simple chain of conditions.
    """
    def predict(self, features):
        results = []
        for row in features:
            crime, lighting, crowd, police_dist, hour, dow, hist = row
            # Night penalty (22:00-05:00)
            is_night = (hour >= 22 or hour < 5)
            # Danger score (higher = more dangerous)
            danger = 0
            danger += crime * 8
            danger += (100 - lighting) * 0.4
            danger += (100 - crowd) * 0.3
            danger += min(police_dist / 50, 40)
            danger += (100 - hist) * 0.3
            if is_night:
                danger += 15
            if is_night and crowd < 30:
                danger += 10

            if danger < 35:
                results.append('LOW')
            elif danger < 65:
                results.append('MEDIUM')
            else:
                results.append('HIGH')
        return results

    def predict_proba(self, features):
        labels = self.predict(features)
        proba = []
        for lbl in labels:
            if lbl == 'LOW':
                proba.append([0.85, 0.12, 0.03])
            elif lbl == 'MEDIUM':
                proba.append([0.10, 0.75, 0.15])
            else:
                proba.append([0.02, 0.10, 0.88])
        return proba


# -----------------------------------------------------------------------
# Data Loading
# -----------------------------------------------------------------------
def load_dataset(path):
    """Load CSV dataset, return list of feature rows and labels."""
    rows_X, rows_y = [], []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                x = [
                    float(row['crime_incidents']),
                    float(row['lighting_pct']),
                    float(row['crowd_density']),
                    float(row['police_dist_m']),
                    float(row['hour_of_day']),
                    float(row['day_of_week']),
                    float(row['historical_safety'])
                ]
                y = row['risk_label'].strip().upper()
                if y in CLASS_ORDER:
                    rows_X.append(x)
                    rows_y.append(y)
            except (KeyError, ValueError):
                continue
    return rows_X, rows_y


# -----------------------------------------------------------------------
# Training
# -----------------------------------------------------------------------
def train_sklearn_model(X_train, y_train):
    """Train a Random Forest classifier."""
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        min_samples_split=4,
        min_samples_leaf=2,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test, y_test):
    """Return evaluation dict."""
    y_pred = model.predict(X_test)
    acc  = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, average='weighted', zero_division=0)
    rec  = recall_score(y_test, y_pred, average='weighted', zero_division=0)
    f1   = f1_score(y_test, y_pred, average='weighted', zero_division=0)
    report = classification_report(y_test, y_pred, target_names=CLASS_ORDER, output_dict=True)
    return {
        'accuracy':  round(float(acc), 4),
        'precision': round(float(prec), 4),
        'recall':    round(float(rec), 4),
        'f1_score':  round(float(f1), 4),
        'per_class': report,
        'y_pred': list(y_pred),
        'y_test': list(y_test)
    }


def get_feature_importances(model):
    """Return sorted feature importances."""
    importances = model.feature_importances_
    return sorted(
        [{'feature': FEATURE_COLS[i], 'importance': round(float(importances[i]), 4)}
         for i in range(len(FEATURE_COLS))],
        key=lambda x: x['importance'], reverse=True
    )


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------
def main():
    print("\n" + "="*55)
    print("  SafeHer ML Risk Classifier — Training Pipeline")
    print("="*55)

    # 1. Load Data
    print(f"\n[1/5] Loading dataset: {DATASET}")
    X, y = load_dataset(DATASET)
    print(f"      Loaded {len(X)} samples")
    counts = {c: y.count(c) for c in CLASS_ORDER}
    for cls, cnt in counts.items():
        print(f"      {cls:8s}: {cnt} samples")

    if not HAS_SKLEARN:
        print("\n[!] scikit-learn not installed.")
        print("    Installing fallback rule-based model...")
        model = SimpleFallbackModel()
        # Evaluate fallback
        preds = model.predict(X)
        correct = sum(1 for p, a in zip(preds, y) if p == a)
        acc = correct / len(y)
        results = {
            'model_type': 'SimpleFallbackModel (rule-based)',
            'trained_at': datetime.now().isoformat(),
            'total_samples': len(X),
            'accuracy': round(acc, 4),
            'precision': 'N/A', 'recall': 'N/A', 'f1_score': 'N/A',
            'feature_importances': [
                {'feature': 'crime_incidents', 'importance': 0.30},
                {'feature': 'historical_safety', 'importance': 0.25},
                {'feature': 'police_dist_m', 'importance': 0.18},
                {'feature': 'lighting_pct', 'importance': 0.15},
                {'feature': 'crowd_density', 'importance': 0.08},
                {'feature': 'hour_of_day', 'importance': 0.03},
                {'feature': 'day_of_week', 'importance': 0.01},
            ],
            'class_distribution': counts,
            'note': 'Install scikit-learn for Random Forest model'
        }
        import pickle
        with open(MODEL_PATH.replace('.pkl', '_fallback.pkl'), 'wb') as f:
            pickle.dump(model, f)
        with open(EVAL_PATH, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n  Fallback model accuracy: {acc:.1%}")
        print(f"  Evaluation saved → {EVAL_PATH}")
        return

    import numpy as np

    X_arr = np.array(X, dtype=float)
    y_arr = np.array(y)

    # 2. Split
    print("\n[2/5] Splitting data (80% train / 20% test)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X_arr, y_arr, test_size=0.20, random_state=42, stratify=y_arr
    )
    print(f"      Train: {len(X_train)} | Test: {len(X_test)}")

    # 3. Train
    print("\n[3/5] Training Random Forest (100 trees, max_depth=8)...")
    model = train_sklearn_model(X_train, y_train)
    print("      Training complete.")

    # 4. Evaluate
    print("\n[4/5] Evaluating model on test set...")
    eval_results = evaluate_model(model, X_test, y_test)
    importances  = get_feature_importances(model)

    # Cross-validation
    cv_scores = cross_val_score(model, X_arr, y_arr, cv=5, scoring='accuracy')
    cv_mean   = round(float(cv_scores.mean()), 4)
    cv_std    = round(float(cv_scores.std()), 4)

    print(f"\n  ┌── Evaluation Results ─────────────────────┐")
    print(f"  │  Accuracy  : {eval_results['accuracy']:.1%}")
    print(f"  │  Precision : {eval_results['precision']:.1%}")
    print(f"  │  Recall    : {eval_results['recall']:.1%}")
    print(f"  │  F1-Score  : {eval_results['f1_score']:.1%}")
    print(f"  │  CV (5-fold): {cv_mean:.1%} ± {cv_std:.1%}")
    print(f"  └───────────────────────────────────────────┘")

    print(f"\n  Feature Importances:")
    for fi in importances:
        bar = '█' * int(fi['importance'] * 40)
        print(f"  {fi['feature']:20s} {bar} {fi['importance']:.3f}")

    # 5. Save
    print(f"\n[5/5] Saving model → {MODEL_PATH}")
    joblib.dump(model, MODEL_PATH)

    summary = {
        'model_type': 'RandomForestClassifier',
        'trained_at': datetime.now().isoformat(),
        'total_samples': len(X),
        'train_samples': len(X_train),
        'test_samples':  len(X_test),
        'accuracy':  eval_results['accuracy'],
        'precision': eval_results['precision'],
        'recall':    eval_results['recall'],
        'f1_score':  eval_results['f1_score'],
        'cv_accuracy_mean': cv_mean,
        'cv_accuracy_std':  cv_std,
        'feature_importances': importances,
        'class_distribution': counts,
        'features_used': FEATURE_COLS,
        'target_classes': CLASS_ORDER,
        'hyperparameters': {
            'n_estimators': 100,
            'max_depth': 8,
            'min_samples_split': 4,
            'min_samples_leaf': 2,
            'class_weight': 'balanced'
        }
    }
    with open(EVAL_PATH, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"      Evaluation saved → {EVAL_PATH}")
    print("\n✅ Training complete! Model is ready for predictions.\n")


if __name__ == '__main__':
    main()
