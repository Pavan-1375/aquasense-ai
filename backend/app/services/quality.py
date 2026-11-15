from dataclasses import dataclass


@dataclass(frozen=True)
class StandardLimit:
    ideal: float
    permissible: float
    weight: float


# Four-parameter screening profile. The score is a lower-is-better normalized
# deviation score, not a regulatory WQI or potability certification.
SCREENING_PROFILE = {
    "ph": StandardLimit(7.0, 2.0, 0.25),
    "tds_mg_l": StandardLimit(0.0, 500.0, 0.25),
    "turbidity_ntu": StandardLimit(0.0, 5.0, 0.25),
    "temperature_c": StandardLimit(25.0, 15.0, 0.25),
}


def calculate_wqi(values: dict[str, float | None]) -> tuple[float | None, str | None, list[str]]:
    contributions: list[tuple[float, float]] = []
    missing: list[str] = []
    for key, limit in SCREENING_PROFILE.items():
        value = values.get(key)
        if value is None:
            missing.append(key)
            continue
        if key == "ph":
            distance = max(0.0, 6.5 - float(value), float(value) - 8.5)
            quality = distance / limit.permissible * 100
        else:
            quality = abs(float(value) - limit.ideal) / max(limit.permissible, 0.001) * 100
        contributions.append((min(250.0, quality), limit.weight))
    if not contributions:
        return None, None, missing
    score = sum(value * weight for value, weight in contributions) / sum(weight for _, weight in contributions)
    label = "Excellent" if score <= 25 else "Good" if score <= 50 else "Poor" if score <= 75 else "Very poor" if score <= 100 else "Unsuitable"
    return round(score, 2), label, missing

