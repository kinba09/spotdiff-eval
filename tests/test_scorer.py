import json
import tempfile
import unittest
from pathlib import Path

from spotdiff_eval.scorer import evaluate_manifest, match_differences
from spotdiff_eval.schema import Difference, SchemaError, load_annotation_differences, load_predictions


ROOT = Path(__file__).resolve().parents[1]


class ScorerTests(unittest.TestCase):
    def _write_predictions(self, value):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "predictions.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return directory, path

    def _perfect_predictions(self):
        manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
        items = []
        for raw_item in manifest["items"]:
            annotation_path = ROOT / raw_item["annotation"]
            differences = load_annotation_differences(annotation_path)
            items.append(
                {
                    "item_id": raw_item["item_id"],
                    "differences": [difference.to_dict() for difference in differences],
                }
            )
        return {"schema_version": "1.0", "model": "perfect-baseline", "items": items}

    def test_perfect_predictions_score_one_hundred_percent(self):
        directory, path = self._write_predictions(self._perfect_predictions())
        try:
            report = evaluate_manifest(ROOT / "data/manifest.json", path)
        finally:
            directory.cleanup()
        self.assertEqual(report["metrics"]["recall"], 1.0)
        self.assertEqual(report["metrics"]["precision"], 1.0)
        self.assertEqual(report["metrics"]["attribute_accuracy"], 1.0)
        self.assertEqual(report["metrics"]["overall_score"], 1.0)

    def test_all_missed_predictions_score_zero(self):
        manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
        value = {
            "schema_version": "1.0",
            "model": "empty-baseline",
            "items": [{"item_id": item["item_id"], "differences": []} for item in manifest["items"]],
        }
        directory, path = self._write_predictions(value)
        try:
            report = evaluate_manifest(ROOT / "data/manifest.json", path)
        finally:
            directory.cleanup()
        self.assertEqual(report["metrics"]["recall"], 0.0)
        self.assertEqual(report["metrics"]["precision"], 0.0)
        self.assertEqual(report["metrics"]["overall_score"], 0.0)

    def test_extra_prediction_reduces_precision(self):
        value = {
            "schema_version": "1.0",
            "items": [
                {
                    "item_id": "scene_0001_playground",
                    "differences": [
                        {"kind": "object_removed", "subject": "playground_flag"},
                        {"kind": "object_added", "subject": "nonexistent_object"},
                    ],
                }
            ],
        }
        directory, path = self._write_predictions(value)
        try:
            report = evaluate_manifest(ROOT / "data/manifest.json", path)
        finally:
            directory.cleanup()
        item = report["items"][0]
        self.assertEqual(item["counts"]["correct_differences"], 1)
        self.assertEqual(item["counts"]["extra_predictions"], 1)
        self.assertEqual(item["metrics"]["precision"], 0.5)

    def test_wrong_attribute_is_detected_but_penalized(self):
        value = {
            "schema_version": "1.0",
            "items": [
                {
                    "item_id": "scene_0001_playground",
                    "differences": [
                        {
                            "kind": "attribute_change",
                            "subject": "boy_shirt",
                            "attribute": "shirt_design",
                            "from": "star",
                            "to": "polka dots",
                        }
                    ],
                }
            ],
        }
        directory, path = self._write_predictions(value)
        try:
            report = evaluate_manifest(ROOT / "data/manifest.json", path)
        finally:
            directory.cleanup()
        item = report["items"][0]
        self.assertEqual(item["counts"]["correct_differences"], 1)
        self.assertLess(item["metrics"]["attribute_accuracy"], 1.0)

    def test_exact_structured_match(self):
        expected = [Difference.from_dict({"id": "d1", "kind": "object_removed", "subject": "flag"})]
        predicted = [Difference.from_dict({"kind": "object_removed", "subject": "flag"})]
        matches, missed, extra = match_differences(predicted, expected)
        self.assertEqual(len(matches), 1)
        self.assertEqual(missed, [])
        self.assertEqual(extra, [])

    def test_one_to_one_matching_reports_missed_and_extra(self):
        expected = [Difference.from_dict({"id": "d1", "kind": "object_added", "subject": "small_cloud"})]
        predicted = [
            Difference.from_dict({"kind": "object_added", "subject": "small cloud"}),
            Difference.from_dict({"kind": "object_removed", "subject": "flag"}),
        ]
        matches, missed, extra = match_differences(predicted, expected)
        self.assertEqual(len(matches), 1)
        self.assertEqual(missed, [])
        self.assertEqual(extra, [1])

    def test_low_similarity_prediction_is_not_counted_as_match(self):
        expected = [Difference.from_dict({"id": "d1", "kind": "attribute_change", "subject": "green_jacket_person_hand", "attribute": "occlusion"})]
        predicted = [Difference.from_dict({"kind": "attribute_change", "subject": "boy_in_pink_shirt", "attribute": "posture"})]
        matches, missed, extra = match_differences(predicted, expected)
        self.assertEqual(matches, [])
        self.assertEqual(missed, [0])
        self.assertEqual(extra, [0])

    def test_attribute_accuracy_is_separate_from_detection(self):
        expected = [Difference.from_dict({"kind": "attribute_change", "subject": "shirt", "attribute": "color", "from": "blue", "to": "red"})]
        predicted = [Difference.from_dict({"kind": "attribute_change", "subject": "shirt", "attribute": "color", "from": "blue", "to": "green"})]
        matches, _, _ = match_differences(predicted, expected)
        self.assertEqual(len(matches), 1)
        self.assertLess(matches[0].attribute_accuracy, 1.0)

    def test_count_mismatch_is_penalized_for_added_objects(self):
        expected = [Difference.from_dict({"id": "d1", "kind": "object_added", "subject": "tree_flower", "count": 4})]
        predicted = [Difference.from_dict({"kind": "object_added", "subject": "tree flowers", "count": 3})]
        matches, _, _ = match_differences(predicted, expected)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].attribute_accuracy, 0.0)

    def test_prediction_schema_rejects_duplicate_items(self):
        with self.assertRaises(SchemaError):
            load_predictions_from_value({
                "schema_version": "1.0",
                "items": [
                    {"item_id": "scene", "differences": []},
                    {"item_id": "scene", "differences": []},
                ],
            })

    def test_prediction_schema_rejects_unknown_kind(self):
        with self.assertRaises(SchemaError):
            load_predictions_from_value({
                "schema_version": "1.0",
                "items": [{"item_id": "scene", "differences": [{"kind": "unknown", "subject": "thing"}]}],
            })

    def test_example_evaluation_runs(self):
        report = evaluate_manifest(ROOT / "data/manifest.json", ROOT / "predictions/example.json")
        self.assertEqual(report["counts"]["items"], 10)
        self.assertEqual(report["counts"]["correct_differences"], 2)
        self.assertIn("overall_score", report["metrics"])


def load_predictions_from_value(value):
    from spotdiff_eval.schema import PredictionDocument

    return PredictionDocument.from_dict(value)


if __name__ == "__main__":
    unittest.main()
