from dataclasses import dataclass


@dataclass(frozen=True)
class StandardLimit:
    ideal: float
    permissible: float
    weight: float


# Explicit weighted-arithmetic screening profile. These values are a configurable
# project profile and must be reviewed against the laboratory standard used by the
# deployment before health-critical decisions.
SCREENING_PROFILE = {
    "ph": StandardLimit(7.0, 8.5, 1.0),
    "tds_mg_l": StandardLimit(0.0, 500.0, 1.0),
    "ec_us_cm": StandardLimit(0.0, 1500.0, 0.8),
    "turbidity_ntu": StandardLimit(0.0, 5.0, 1.0),
    "hardness_mg_l": StandardLimit(0.0, 200.0, 0.8),
    "chloride_mg_l": StandardLimit(0.0, 250.0, 0.8),
}


def calculate_wqi(values: dict[str, float | None]) -> tuple[float | None, str | None, list[str]]:
    contributions: list[tuple[float, float]] = []
    missing: list[str] = []
    for key, limit in SCREENING_PROFILE.items():
        value = values.get(key)
        if value is None:
            missing.append(key)
            continue
        quality = abs(float(value) - limit.ideal) / max(limit.permissible - limit.ideal, 0.001) * 100
        contributions.append((min(250.0, quality), limit.weight))
    if not contributions:
        return None, None, missing
    score = sum(value * weight for value, weight in contributions) / sum(weight for _, weight in contributions)
    label = "Excellent" if score <= 25 else "Good" if score <= 50 else "Poor" if score <= 75 else "Very poor" if score <= 100 else "Unsuitable"
    return round(score, 2), label, missing

