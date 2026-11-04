from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBClassifier
except ImportError:
    XGBClassifier = None


FEATURE_COLUMNS = [
    "pH",
    "TDS_mg_L",
    "Turbidity_NTU",
    "Temperature_C",
]

SOURCE_COLUMNS = {
    "pH": "Potential of Hydrogen (pH)",
    "TDS_mg_L": "Total Dissolved Solids (mg/L)",
    "Turbidity_NTU": "Turbidity (NTU)",
    "Temperature_C": "Temperature (°C)",
}

LIMITS = {
    "pH": {"ideal": 7.0, "lower": 6.5, "upper": 8.5, "weight_limit": 1.5},
    "TDS_mg_L": {"ideal": 0.0, "upper": 500.0, "weight_limit": 500.0},
    "Turbidity_NTU": {"ideal": 0.0, "upper": 5.0, "weight_limit": 5.0},
    "Temperature_C": {"ideal": 25.0, "upper": 40.0, "weight_limit": 15.0},
}

CLASS_BANDS = [0.0, 25.0, 50.0, 75.0, 100.0, float("inf")]
CLASS_LABELS = ["Excellent", "Good", "Poor", "Very poor", "Unsuitable"]


def load_quality_data(paths: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_csv(path, low_memory=False)
        missing_columns = [source for source in SOURCE_COLUMNS.values() if source not in frame.columns]
        if missing_columns:
            raise ValueError(f"{path.name} is missing required columns: {missing_columns}")
        renamed = frame.rename(columns={source: target for target, source in SOURCE_COLUMNS.items()})
        renamed["source_file"] = path.name
        frames.append(renamed)
    combined = pd.concat(frames, ignore_index=True)
    for column in FEATURE_COLUMNS:
        combined[column] = pd.to_numeric(combined[column], errors="coerce")
    complete = combined.dropna(subset=FEATURE_COLUMNS).copy()
    complete = complete[(complete["pH"] >= 0) & (complete["pH"] <= 14)]
    complete = complete[(complete["TDS_mg_L"] >= 0) & (complete["Turbidity_NTU"] >= 0)]
    return complete


def parameter_subindex(values: pd.Series, name: str) -> pd.Series:
    limits = LIMITS[name]
    if name == "pH":
        high_side = values >= limits["ideal"]
        high_index = 100.0 * (values - limits["ideal"]) / (limits["upper"] - limits["ideal"])
        low_index = 100.0 * (limits["ideal"] - values) / (limits["ideal"] - limits["lower"])
        return pd.Series(np.where(high_side, high_index, low_index), index=values.index).clip(lower=0)
    return 100.0 * (values - limits["ideal"]) / limits["upper"]


def calculate_wqi(frame: pd.DataFrame) -> pd.Series:
    weighted_subindices = []
    weights = []
    for name in FEATURE_COLUMNS:
        subindex = parameter_subindex(frame[name], name)
        weight = 1.0 / LIMITS[name]["weight_limit"]
        weighted_subindices.append(subindex * weight)
        weights.append(weight)
    return sum(weighted_subindices) / sum(weights)


def make_labels(wqi: pd.Series) -> pd.Series:
    return pd.cut(wqi, bins=CLASS_BANDS, labels=CLASS_LABELS, include_lowest=True, right=True).astype(str)


def build_candidates() -> dict[str, Any]:
    candidates: dict[str, Any] = {
        "logistic_regression": Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=2500, class_weight="balanced", random_state=42)),
        ]),
        "random_forest": RandomForestClassifier(
            n_estimators=400, min_samples_leaf=2, class_weight="balanced_subsample", n_jobs=1, random_state=42
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=400, min_samples_leaf=2, class_weight="balanced", n_jobs=1, random_state=42
        ),
    }
    if XGBClassifier is not None:
        candidates["xgboost"] = XGBClassifier(
            n_estimators=400,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_lambda=2.0,
            objective="multi:softprob",
            eval_metric="mlogloss",
            n_jobs=1,
            random_state=42,
        )
    return candidates


def feature_importance(model: Any) -> dict[str, float]:
    estimator = model.named_steps["model"] if isinstance(model, Pipeline) else model
    if hasattr(estimator, "feature_importances_"):
        values = estimator.feature_importances_
    else:
        values = np.abs(estimator.coef_).mean(axis=0)
    return {name: round(float(value), 6) for name, value in zip(FEATURE_COLUMNS, values)}


def evaluate_candidates(X: pd.DataFrame, y: pd.Series) -> tuple[str, dict[str, dict[str, float]]]:
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    results: dict[str, dict[str, float]] = {}
    for name, estimator in build_candidates().items():
        predictions = cross_val_predict(estimator, X, y, cv=folds, n_jobs=1)
        results[name] = {
            "accuracy": round(float(accuracy_score(y, predictions)), 4),
            "macro_f1": round(float(f1_score(y, predictions, average="macro", zero_division=0)), 4),
            "weighted_f1": round(float(f1_score(y, predictions, average="weighted", zero_division=0)), 4),
            "balanced_accuracy": round(float(balanced_accuracy_score(y, predictions)), 4),
        }
    best_name = max(results, key=lambda name: (results[name]["macro_f1"], results[name]["balanced_accuracy"]))
    return best_name, results


def train(paths: list[Path], output_dir: Path) -> dict[str, Any]:
    frame = load_quality_data(paths)
    frame["wqi"] = calculate_wqi(frame)
    frame["label"] = make_labels(frame["wqi"])
    X = frame[FEATURE_COLUMNS]
    class_to_id = {label: index for index, label in enumerate(CLASS_LABELS)}
    y = frame["label"].map(class_to_id).astype(int)
    best_name, metrics = evaluate_candidates(X, y)
    final_model = build_candidates()[best_name]
    final_model.fit(X, y)

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model": final_model,
        "model_type": best_name,
        "feature_order": FEATURE_COLUMNS,
        "classes": CLASS_LABELS,
        "class_mapping": {str(index): label for label, index in class_to_id.items()},
        "formula": "Weighted arithmetic screening score over pH, TDS, turbidity, and temperature",
        "limits": LIMITS,
        "source_columns": SOURCE_COLUMNS,
    }
    joblib.dump(artifact, output_dir / "quality_model.joblib")
    metadata = {
        "model_type": best_name,
        "feature_order": FEATURE_COLUMNS,
        "classes": CLASS_LABELS,
        "formula": artifact["formula"],
        "limits": LIMITS,
        "source_files": [str(path) for path in paths],
        "complete_rows": int(len(frame)),
        "label_distribution": {str(key): int(value) for key, value in frame["label"].value_counts().to_dict().items()},
        "wqi_range": [round(float(frame["wqi"].min()), 4), round(float(frame["wqi"].max()), 4)],
        "feature_importance": feature_importance(final_model),
        "metrics": metrics,
        "limitations": [
            "Labels are derived from the documented screening formula, not clinician- or regulator-confirmed classes.",
            "The supplied CGWB chemistry files are not compatible with this four-parameter contract because they do not provide turbidity and temperature.",
            "The result is not a potability certification and does not include microbiological testing.",
        ],
    }
    (output_dir / "quality_model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("ml/artifacts"))
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    metadata = train(args.paths, args.output_dir)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
