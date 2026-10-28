from datetime import datetime, timezone


def fallback_forecast(levels: list[float], horizon_days: int = 7) -> dict:
    """Transparent baseline forecast; never presented as a trained model output."""
    if not levels:
        return {"model_name": "transparent-fallback", "model_version": "fallback-0.1", "status": "insufficient_data"}
    recent = levels[-min(10, len(levels)):]
    slope = (recent[-1] - recent[0]) / max(len(recent) - 1, 1)
    predicted = max(0.0, min(100.0, recent[-1] + slope * horizon_days))
    spread = max(3.0, abs(slope) * horizon_days * 1.5)
    risk = "high" if predicted < 25 else "medium" if predicted < 45 else "low"
    return {
        "model_name": "transparent-fallback",
        "model_version": "fallback-0.1",
        "predicted_level_percent": round(predicted, 2),
        "lower_percent": round(max(0.0, predicted - spread), 2),
        "upper_percent": round(min(100.0, predicted + spread), 2),
        "confidence": 0.35 if len(levels) < 10 else 0.5,
        "risk": risk,
        "horizon_days": horizon_days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Fallback trend baseline used because a compatible trained forecasting artifact was not supplied.",
    }

