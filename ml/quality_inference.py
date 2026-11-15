from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

ACTIVE_FEATURE_ORDER = ["pH", "TDS_mg_L", "Turbidity_NTU", "Temperature_C"]


def validate_feature_vector(payload: dict[str, Any], artifact: dict[str, Any]) -> list[float]:
    expected = artifact["feature_order"]
    if expected != ACTIVE_FEATURE_ORDER:
        raise ValueError(
            "Quality model artifact is incompatible with the active four-parameter contract. "
            f"Artifact={expected}; expected={ACTIVE_FEATURE_ORDER}. Retrain the model with the active dataset."
        )
    missing = [name for name in expected if name not in payload]
    extra = [name for name in payload if name not in expected]
    if missing or extra:
        raise ValueError(f"Feature contract mismatch. Missing={missing}; extra={extra}; expected_order={expected}")
    values: list[float] = []
    for name in expected:
        value = payload[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
            raise ValueError(f"Feature {name} must be a finite numeric value")
        limits = artifact["limits"][name]
        # Readings outside the preferred guideline range must still be classified and
        # flagged. Only impossible sensor values are rejected at this layer.
        lower = limits.get("sensor_lower", 0.0)
        upper = limits.get("upper", 1e12)
        if value < lower or value > upper * 20:
            raise ValueError(f"Feature {name}={value} is outside the accepted sensor range")
        values.append(float(value))
    return values


def predict_quality(payload: dict[str, Any], artifact_path: str | Path) -> dict[str, Any]:
    artifact = joblib.load(artifact_path)
    values = validate_feature_vector(payload, artifact)
    frame = pd.DataFrame([values], columns=artifact["feature_order"])
    raw_prediction = artifact["model"].predict(frame)[0]
    encoded = int(raw_prediction) if isinstance(raw_prediction, (int, np.integer)) else raw_prediction
    probabilities = artifact["model"].predict_proba(frame)[0]
    if isinstance(encoded, str):
        label = encoded
        probability_labels = list(getattr(artifact["model"], "classes_", artifact.get("classes", [])))
        probabilities_by_label = {str(name): round(float(probability), 4) for name, probability in zip(probability_labels, probabilities)}
    else:
        label = artifact["class_mapping"][str(encoded)]
        probabilities_by_label = {artifact["class_mapping"][str(index)]: round(float(probability), 4) for index, probability in enumerate(probabilities)}
    return {
        "class": label,
        "confidence": round(float(np.max(probabilities)), 4),
        "probabilities": probabilities_by_label,
        "feature_order": artifact["feature_order"],
        "model_type": artifact.get("model_type", "xgboost"),
    }
