import json
import unittest
from datetime import datetime

from bridge.serial_bridge import LegacyTextParser, parse_message


class SerialBridgeTests(unittest.TestCase):
    def test_parses_firmware_packet_with_millis_timestamp_string(self) -> None:
        packet = {
            "device_id": "ESP32-001",
            "timestamp": "12345",
            "distance_cm": 57.8,
            "water_depth_cm": 12.4,
            "water_level_percent": 21.5,
            "temperature_c": None,
        }
        result = parse_message(json.dumps(packet))
        self.assertEqual(result["device_id"], "ESP32-001")
        self.assertEqual(result["distance_cm"], 57.8)
        self.assertEqual(result["water_depth_cm"], 12.4)
        self.assertEqual(result["water_level_percent"], 21.5)
        self.assertIsNotNone(datetime.fromisoformat(result["timestamp"]))

    def test_preserves_iso_timestamp(self) -> None:
        packet = {"device_id": "ESP32-001", "timestamp": "2026-11-19T07:55:42+00:00", "distance_cm": 18.0}
        self.assertEqual(parse_message(json.dumps(packet))["timestamp"], packet["timestamp"])

    def test_legacy_oled_text_is_collected_as_one_reading(self) -> None:
        parser = LegacyTextParser("ESP32-001")
        self.assertIsNone(parser.parse("Sensor distance: 57.8 cm"))
        self.assertIsNone(parser.parse("Water level: 12.4 cm"))
        result = parser.parse("Water percentage: 21.5 %")
        self.assertEqual(result["device_id"], "ESP32-001")
        self.assertEqual(result["distance_cm"], 57.8)
        self.assertEqual(result["water_depth_cm"], 12.4)
        self.assertEqual(result["water_level_percent"], 21.5)

    def test_rejects_packet_without_sensor_measurement(self) -> None:
        packet = {"device_id": "ESP32-001", "timestamp": "12345", "distance_cm": None, "water_level_percent": None, "water_depth_cm": None}
        with self.assertRaisesRegex(ValueError, "at least one groundwater measurement"):
            parse_message(json.dumps(packet))


if __name__ == "__main__":
    unittest.main()
