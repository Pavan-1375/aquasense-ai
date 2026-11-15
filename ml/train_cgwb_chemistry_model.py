"""Train the dataset-compatible five-parameter CGWB chemistry model.

This is intentionally separate from the active four-sensor screening contract.
Labels are formula-derived screening classes, not laboratory truth labels.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

FEATURES = ["pH", "EC_uS_cm", "TDS_mg_L", "Total_Hardness_mgCaCO3_L", "Chloride_mg_L"]
SOURCE = {"pH": "Potential of Hydrogen (pH)", "EC_uS_cm": "Electric Conductivity (μS/cm)", "TDS_mg_L": "Total Dissolved Solids (mg/L)", "Total_Hardness_mgCaCO3_L": "Total Hardness (mgCaCO3/L)", "Chloride_mg_L": "Chloride (mg/L)"}
LIMITS = {"pH": (6.5, 8.5), "EC_uS_cm": (0, 1500), "TDS_mg_L": (0, 500), "Total_Hardness_mgCaCO3_L": (0, 200), "Chloride_mg_L": (0, 250)}
LABELS = ["Excellent", "Good", "Poor", "Very poor", "Unsuitable"]


def load(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        frame = pd.read_csv(path, low_memory=False).rename(columns={value: key for key, value in SOURCE.items()})
        missing = [column for column in FEATURES if column not in frame]
        if missing:
            raise ValueError(f"{path} missing {missing}")
        frames.append(frame[FEATURES])
    data = pd.concat(frames, ignore_index=True)
    for column in FEATURES:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna()
    for column, (lower, upper) in LIMITS.items():
        data = data[(data[column] >= lower if column == "pH" else data[column] >= 0)]
    return data


def labels(data: pd.DataFrame) -> pd.Series:
    penalties = []
    for column, (lower, upper) in LIMITS.items():
        if column == "pH":
            penalty = ((data[column] < lower) * (lower - data[column]) + (data[column] > upper) * (data[column] - upper)) / 2
        else:
            penalty = data[column] / max(upper, 1) * 100
        penalties.append(penalty)
    score = sum(penalties) / len(penalties)
    return pd.cut(score, [-1, 25, 50, 75, 100, float("inf")], labels=LABELS).astype(str)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("ml/artifacts/cgwb_chemistry"))
    args = parser.parse_args()
    data = load(args.paths)
    y = labels(data)
    model = RandomForestClassifier(n_estimators=400, min_samples_leaf=2, class_weight="balanced_subsample", random_state=42, n_jobs=1)
    predictions = cross_val_predict(model, data[FEATURES], y, cv=StratifiedKFold(5, shuffle=True, random_state=42))
    model.fit(data[FEATURES], y)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "model_type": "random_forest", "feature_order": FEATURES, "classes": LABELS, "class_mapping": {str(i): label for i, label in enumerate(model.classes_)}, "units": {"EC_uS_cm": "µS/cm", "TDS_mg_L": "mg/L", "Total_Hardness_mgCaCO3_L": "mg/L as CaCO3", "Chloride_mg_L": "mg/L"}, "source": "CGWB chemistry files", "label_source": "formula-derived screening labels; not laboratory truth"}, args.output_dir / "quality_model.joblib")
    metadata = {"contract": "cgwb-chemistry-5", "feature_order": FEATURES, "rows": len(data), "classes": sorted(y.unique().tolist()), "metrics": {"accuracy": accuracy_score(y, predictions), "balanced_accuracy": balanced_accuracy_score(y, predictions), "macro_f1": f1_score(y, predictions, average="macro")}, "limitations": ["Formula-derived labels are not laboratory labels.", "This model is not compatible with the four-sensor pH/TDS/turbidity/temperature contract.", "This model is not a potability certification."]}
    (args.output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
