"""Generate a deterministic 30-day groundwater depletion demonstration.

This is presentation/demo data only. It does not represent a sensor, station,
or trained forecasting model.
"""
from datetime import date, timedelta
import json
import sys

sys.path.insert(0, "backend")
from app.services.forecast import fallback_forecast


def main() -> None:
    start = date.today() - timedelta(days=29)
    levels = [round(62.0 - day * 0.52 + (0.35 if day % 3 == 0 else -0.15 if day % 3 == 1 else 0.0), 2) for day in range(30)]
    readings = [{"date": (start + timedelta(days=index)).isoformat(), "water_level_percent": level, "source": "DEMO"} for index, level in enumerate(levels)]
    recent = levels[-7:]
    trend_per_day = round((recent[-1] - recent[0]) / 6, 2)
    forecast = fallback_forecast(levels, horizon_days=7)
    result = {
        "label": "DEMO ONLY — artificial 30-day monitoring",
        "readings": readings,
        "summary": {
            "first_level_percent": levels[0],
            "last_level_percent": levels[-1],
            "change_percent_points": round(levels[-1] - levels[0], 2),
            "seven_day_trend_percent_points_per_day": trend_per_day,
            "seven_day_forecast": forecast,
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
