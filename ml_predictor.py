"""
ml_predictor.py - SafeHer ML Risk Level Prediction Module

Loads the trained Random Forest model and exposes predict_risk()
for use by Flask API endpoints. Includes a rule-based fallback when
scikit-learn is not available.

How the model works (for project demo):
-----------------------------------------
1. We trained a Random Forest on 300 labelled route segments.
2. Each route segment has 7 features:
     crime_incidents, lighting_pct, crowd_density, police_dist_m,
     hour_of_day, day_of_week, historical_safety
3. The forest builds 100 decision trees and votes on the risk class.
4. Output: LOW / MEDIUM / HIGH with a confidence score (0-1).
5. We blend this ML prediction with our existing weighted safety score
   for a combined final score.

Feature Importance (approximate from trained model):
  crime_incidents    ~30%  — Most influential
  historical_safety  ~25%  — Past track record
  police_dist_m      ~18%  — Emergency response proximity
  lighting_pct       ~15%  — Visibility factor
  crowd_density      ~8%   — People around = safer
  hour_of_day        ~3%   — Night vs. day context
  day_of_week        ~1%   — Weekend patterns
"""

import os
import json
import logging
import math
from datetime import datetime

log = logging.getLogger(__name__)

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'safeher_risk_model.pkl')
EVAL_PATH  = os.path.join(BASE_DIR, 'ml_evaluation.json')

# Risk class definitions
RISK_CLASSES   = ['LOW', 'MEDIUM', 'HIGH']
RISK_COLORS    = {'LOW': '#10B981', 'MEDIUM': '#F59E0B', 'HIGH': '#EF4444'}
RISK_ICONS     = {'LOW': '🟢', 'MEDIUM': '🟡', 'HIGH': '🔴'}
RISK_ADVICE    = {
    'LOW':    'Route segment is safe. Normal precautions apply.',
    'MEDIUM': 'Exercise caution. Prefer this route in daylight or with company.',
    'HIGH':   'High risk detected. Strongly consider an alternative route.'
}

# Loaded model cache
_model = None
_model_type = 'none'
_eval_data = {}


# -----------------------------------------------------------------------
# Pure-Python Rule-Based Fallback
# -----------------------------------------------------------------------
class _RuleBasedPredictor:
    """
    Hand-crafted rules that mimic what the trained model learned.
    Used when scikit-learn / joblib is unavailable.
    """
    @staticmethod
    def predict_single(crime, lighting, crowd, police_dist, hour, dow, hist):
        is_night = (hour >= 22 or hour < 5)
        danger = 0
        danger += crime * 8
        danger += (100 - lighting) * 0.40
        danger += (100 - crowd)    * 0.30
        danger += min(police_dist / 50.0, 40)
        danger += (100 - hist)     * 0.30
        if is_night:
            danger += 15
        if is_night and crowd < 30:
            danger += 10

        if danger < 35:
            return 'LOW',    [0.85, 0.12, 0.03]
        elif danger < 65:
            return 'MEDIUM', [0.10, 0.75, 0.15]
        else:
            return 'HIGH',   [0.02, 0.10, 0.88]


# -----------------------------------------------------------------------
# Model Loader
# -----------------------------------------------------------------------
def _load_model():
    global _model, _model_type, _eval_data

    if _model is not None:
        return  # Already loaded

    # Load evaluation summary if available
    if os.path.exists(EVAL_PATH):
        try:
            with open(EVAL_PATH) as f:
                _eval_data = json.load(f)
        except Exception:
            _eval_data = {}

    # Try scikit-learn / joblib first
    try:
        import joblib
        if os.path.exists(MODEL_PATH):
            _model = joblib.load(MODEL_PATH)
            _model_type = 'RandomForest'
            log.info('SafeHer ML: Loaded Random Forest model from %s', MODEL_PATH)
            return
    except Exception as exc:
        log.warning('SafeHer ML: Could not load sklearn model (%s)', exc)

    # Fallback: rule-based
    _model = _RuleBasedPredictor()
    _model_type = 'RuleBased'
    log.warning('SafeHer ML: Using rule-based fallback predictor (run ml_trainer.py to train)')


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------
def predict_risk(
    crime_incidents,
    lighting_pct,
    crowd_density,
    police_dist_m,
    hour_of_day=None,
    day_of_week=None,
    historical_safety=None
):
    """
    Predict the risk level of a route segment.

    Parameters
    ----------
    crime_incidents  : int/float  – Reported incidents in area (0-15)
    lighting_pct     : float      – Street lighting % (0-100)
    crowd_density    : float      – Pedestrian activity (0-100)
    police_dist_m    : float      – Distance to nearest police station (meters)
    hour_of_day      : int        – Hour 0-23 (default: current hour)
    day_of_week      : int        – 0=Mon ... 6=Sun (default: today)
    historical_safety: float      – Past safety score 0-100 (default derived)

    Returns
    -------
    dict with keys: risk_label, confidence, probabilities, explanation,
                    color, icon, advice, model_type, features_used
    """
    _load_model()

    now = datetime.now()
    if hour_of_day is None:
        hour_of_day = now.hour
    if day_of_week is None:
        day_of_week = now.weekday()
    if historical_safety is None:
        # Derive a sensible historical safety from current features
        historical_safety = max(10, min(98,
            (lighting_pct * 0.35) +
            ((100 - crime_incidents * 8) * 0.35) +
            (crowd_density * 0.20) +
            (max(0, 100 - police_dist_m / 25) * 0.10)
        ))

    features = [
        float(crime_incidents),
        float(lighting_pct),
        float(crowd_density),
        float(police_dist_m),
        float(hour_of_day),
        float(day_of_week),
        float(historical_safety)
    ]

    # --- Predict ---
    if _model_type == 'RandomForest':
        try:
            import numpy as np
            x = np.array([features])
            label = _model.predict(x)[0]
            proba = _model.predict_proba(x)[0].tolist()
            confidence = max(proba)
        except Exception as exc:
            log.error('RandomForest predict failed: %s', exc)
            label, proba = _RuleBasedPredictor.predict_single(*features)
            confidence = max(proba)
    else:
        label, proba = _RuleBasedPredictor.predict_single(*features)
        confidence = max(proba)

    # --- Build explanation ---
    explanation = _build_explanation(
        label, crime_incidents, lighting_pct, crowd_density,
        police_dist_m, hour_of_day, historical_safety
    )

    return {
        'risk_label':    label,
        'confidence':    round(confidence, 3),
        'confidence_pct': int(confidence * 100),
        'probabilities': {
            'LOW':    round(proba[0], 3),
            'MEDIUM': round(proba[1], 3),
            'HIGH':   round(proba[2], 3)
        },
        'color':  RISK_COLORS[label],
        'icon':   RISK_ICONS[label],
        'advice': RISK_ADVICE[label],
        'explanation': explanation,
        'model_type': _model_type,
        'features_used': {
            'crime_incidents':   crime_incidents,
            'lighting_pct':      lighting_pct,
            'crowd_density':     crowd_density,
            'police_dist_m':     round(police_dist_m, 1),
            'hour_of_day':       hour_of_day,
            'day_of_week':       day_of_week,
            'historical_safety': round(historical_safety, 1)
        }
    }


def predict_route_risk(route_data):
    """
    Convenience wrapper: accepts a route dict from safety_engine
    and calls predict_risk() with appropriate feature mapping.
    """
    factors = route_data.get('factors', {})
    lighting  = factors.get('lighting', {}).get('percent', 70)
    crime_pct = factors.get('crime',    {}).get('percent', 30)
    crowd     = factors.get('crowd',    {}).get('percent', 60)
    police_m  = factors.get('police',   {}).get('distance_meters', 800)

    if police_m is None:
        police_m = 800

    # Convert crime_pct (incident rate) → incident count estimate
    crime_count = round(crime_pct / 10.0)

    return predict_risk(
        crime_incidents   = crime_count,
        lighting_pct      = lighting,
        crowd_density     = crowd,
        police_dist_m     = police_m,
        historical_safety = route_data.get('score', 60)
    )


def get_model_info():
    """Return model metadata and evaluation results for the UI/API."""
    _load_model()
    return {
        'model_type':        _model_type,
        'model_file_exists': os.path.exists(MODEL_PATH),
        'evaluation':        _eval_data,
        'classes':           RISK_CLASSES,
        'features':          [
            'crime_incidents', 'lighting_pct', 'crowd_density',
            'police_dist_m', 'hour_of_day', 'day_of_week', 'historical_safety'
        ]
    }


# -----------------------------------------------------------------------
# Explanation Builder
# -----------------------------------------------------------------------
def _build_explanation(label, crime, lighting, crowd, police_dist, hour, hist):
    """Generate a human-readable explanation for the prediction."""
    reasons = []

    # Crime
    if crime == 0:
        reasons.append('✅ No crime incidents recorded in this area')
    elif crime <= 2:
        reasons.append(f'⚠️ {int(crime)} minor incident(s) reported nearby')
    else:
        reasons.append(f'🔴 {int(crime)} crime incidents reported — high risk factor')

    # Lighting
    if lighting >= 85:
        reasons.append('✅ Excellent street lighting (≥85%)')
    elif lighting >= 60:
        reasons.append(f'⚠️ Moderate lighting ({int(lighting)}%) — some dark stretches')
    else:
        reasons.append(f'🔴 Poor lighting ({int(lighting)}%) — significant visibility risk')

    # Crowd
    if crowd >= 70:
        reasons.append('✅ High pedestrian activity — safer with people around')
    elif crowd >= 40:
        reasons.append(f'⚠️ Moderate crowd ({int(crowd)}%) — quieter in some sections')
    else:
        reasons.append(f'🔴 Isolated area ({int(crowd)}% crowd) — minimal foot traffic')

    # Police
    if police_dist <= 300:
        reasons.append(f'✅ Police station nearby ({int(police_dist)}m)')
    elif police_dist <= 800:
        reasons.append(f'⚠️ Police station at {int(police_dist)}m — moderate response time')
    else:
        reasons.append(f'🔴 Nearest police is {int(police_dist)}m away — slow response')

    # Time
    is_night = (hour >= 22 or hour < 5)
    if is_night:
        reasons.append(f'🌙 Night travel ({hour:02d}:00) increases risk')
    elif 5 <= hour < 8 or 19 <= hour < 22:
        reasons.append(f'🌆 Evening/early morning travel ({hour:02d}:00)')

    # Historical
    if hist >= 80:
        reasons.append(f'✅ Strong safety history (score {int(hist)}/100)')
    elif hist >= 55:
        reasons.append(f'⚠️ Moderate safety history (score {int(hist)}/100)')
    else:
        reasons.append(f'🔴 Poor safety history (score {int(hist)}/100)')

    return {
        'summary':  f'ML model classified this segment as {label} RISK with {int(max(0.5,hist)/100*100):.0f}% historical basis.',
        'reasons':  reasons,
        'label':    label
    }
