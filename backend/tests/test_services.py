import unittest
from datetime import datetime

from app.models import ReminderSchedule
from app.schemas import UserCreate
from app.services.forecast import fallback_forecast
from app.services.quality import calculate_wqi
from app.services.reminders import next_occurrence
from app.services.rate_limit import InMemoryRateLimiter


class ServiceTests(unittest.TestCase):
    def test_quality_is_explicit_and_classified(self) -> None:
        score, label, missing = calculate_wqi({"ph": 7.2, "tds_mg_l": 250, "ec_us_cm": 500, "hardness_mg_l": 120, "chloride_mg_l": 80})
        self.assertIsNotNone(score)
        self.assertIn(label, {"Excellent", "Good"})
        self.assertIn("turbidity_ntu", missing)

    def test_fallback_forecast_is_transparent(self) -> None:
        result = fallback_forecast([50, 49, 48, 47])
        self.assertEqual(result["model_name"], "transparent-fallback")
        self.assertEqual(result["horizon_days"], 7)
        self.assertIn("note", result)

    def test_weekly_schedule_is_next_week_and_timezone_aware(self) -> None:
        schedule = ReminderSchedule(weekday=0, local_time="09:00", timezone="Asia/Kolkata")
        next_run = next_occurrence(schedule, datetime(2026, 10, 27, 8, 0))
        self.assertEqual(next_run.weekday(), 0)
        self.assertGreater(next_run, datetime(2026, 10, 27, 8, 0))

    def test_registration_normalizes_international_mobile(self) -> None:
        payload = UserCreate(name="Aqua Test", email=" TEST@Example.com ", mobile_number="+91 98765-43210", password="AquaTest-2026!", password_confirmation="AquaTest-2026!")
        self.assertEqual(payload.email, "test@example.com")
        self.assertEqual(payload.mobile_number, "+919876543210")

    def test_rate_limiter_rejects_only_after_limit(self) -> None:
        limiter = InMemoryRateLimiter()
        self.assertTrue(limiter.allow("test", 2, 60))
        self.assertTrue(limiter.allow("test", 2, 60))
        self.assertFalse(limiter.allow("test", 2, 60))


if __name__ == "__main__":
    unittest.main()

