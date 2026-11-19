import json
import unittest
from pathlib import Path

from ml.quality_inference import ACTIVE_FEATURE_ORDER, validate_feature_vector


class QualityContractTests(unittest.TestCase):
    def test_committed_model_metadata_matches_the_four_sensor_contract(self) -> None:
        metadata_path = Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "quality_model_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["feature_order"], ACTIVE_FEATURE_ORDER)
        self.assertEqual(metadata["classes"], ["Excellent", "Good", "Poor", "Very poor", "Unsuitable"])

    def test_inference_vector_validates_units_order_and_range(self) -> None:
        limits = {
            "pH": {"sensor_lower": 0, "upper": 14},
            "TDS_mg_L": {"sensor_lower": 0, "upper": 5000},
            "Turbidity_NTU": {"sensor_lower": 0, "upper": 1000},
            "Temperature_C": {"sensor_lower": -50, "upper": 100},
        }
        artifact = {"feature_order": ACTIVE_FEATURE_ORDER, "limits": limits}
        values = {"pH": 7.1, "TDS_mg_L": 250, "Turbidity_NTU": 1.5, "Temperature_C": 24}
        self.assertEqual(validate_feature_vector(values, artifact), [7.1, 250.0, 1.5, 24.0])
        with self.assertRaisesRegex(ValueError, "Feature contract mismatch"):
            validate_feature_vector({**values, "EC_uS_cm": 500}, artifact)
        with self.assertRaisesRegex(ValueError, "outside the accepted sensor range"):
            validate_feature_vector({**values, "pH": 300}, artifact)


if __name__ == "__main__":
    unittest.main()
