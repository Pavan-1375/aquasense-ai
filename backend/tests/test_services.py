import unittest
from datetime import datetime
from io import BytesIO

from PIL import Image

from app.models import ReminderSchedule
from app.schemas import UserCreate
from app.services.forecast import fallback_forecast
from app.services.quality import calculate_wqi
from app.services.reminders import next_occurrence
from app.services.rate_limit import InMemoryRateLimiter
from app.services.uploads import sanitize_image_upload


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

    def test_image_upload_reencoding_strips_exif_and_normalizes_extension(self) -> None:
        source = Image.new("RGBA", (8, 6), (20, 80, 120, 128))
        exif = Image.Exif()
        exif[305] = "private camera metadata"
        encoded = BytesIO()
        source.save(encoded, format="PNG", exif=exif)

        sanitized, suffix = sanitize_image_upload(encoded.getvalue(), ".webp")
        with Image.open(BytesIO(sanitized)) as result:
            self.assertEqual(suffix, ".jpg")
            self.assertEqual(result.format, "JPEG")
            self.assertEqual(result.size, (8, 6))
            self.assertEqual(dict(result.getexif()), {})

    def test_png_upload_preserves_alpha_and_strips_metadata(self) -> None:
        source = Image.new("RGBA", (3, 4), (10, 20, 30, 40))
        encoded = BytesIO()
        source.save(encoded, format="PNG")
        sanitized, suffix = sanitize_image_upload(encoded.getvalue(), ".png")
        with Image.open(BytesIO(sanitized)) as result:
            self.assertEqual(suffix, ".png")
            self.assertEqual(result.mode, "RGBA")
            self.assertEqual(result.getpixel((0, 0)), (10, 20, 30, 40))


if __name__ == "__main__":
    unittest.main()

