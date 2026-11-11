import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spotdiff_eval import __version__
from spotdiff_eval.scorer import evaluate_manifest, match_differences
from spotdiff_eval.schema import Difference, SchemaError, load_annotation_differences, load_predictions


ROOT = Path(__file__).resolve().parents[1]


class ScorerTests(unittest.TestCase):
    def _evaluate_single_item(self, expected, predicted, unknown_items=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "annotation.json").write_text(json.dumps({"differences": expected}), encoding="utf-8")
            (root / "manifest.json").write_text(json.dumps({"items": [
                {"item_id": "scene", "annotation": "annotation.json"}
            ]}), encoding="utf-8")
            (root / "predictions.json").write_text(json.dumps({
                "schema_version": "1.0",
                "items": [{"item_id": "scene", "differences": predicted}] + (unknown_items or []),
            }), encoding="utf-8")
            return evaluate_manifest(root / "manifest.json", root / "predictions.json")

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
        self.assertEqual(report["metrics"]["difference_coverage"], 1.0)
        self.assertEqual(report["counts"]["exact_correct_differences"], 61)
        self.assertEqual(report["metrics"]["f1"], 1.0)
        self.assertEqual(report["evaluator_version"], __version__)
        self.assertEqual(report["scoring_method"], "strict_f1")
        self.assertEqual(report["schema_version"], "2.0")
        self.assertNotIn("weights", report)

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

    def test_wrong_attribute_is_diagnostic_only(self):
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
        self.assertEqual(item["counts"]["correct_differences"], 0)
        self.assertEqual(item["counts"]["detected_differences"], 1)
        self.assertEqual(item["counts"]["extra_predictions"], 1)
        self.assertEqual(item["matched"], [])
        self.assertEqual(item["metrics"]["overall_score"], 0.0)
        self.assertLess(item["metrics"]["attribute_accuracy"], 1.0)
        self.assertEqual(item["metrics"]["difference_coverage"], 0.0)

    def test_correct_subject_with_wrong_values_scores_zero(self):
        expected = {"kind": "attribute_change", "subject": "shirt", "attribute": "color", "from": "red", "to": "blue"}
        predicted = dict(expected, **{"from": "green", "to": "yellow"})
        report = self._evaluate_single_item([expected], [predicted])
        self.assertEqual(report["metrics"]["overall_score"], 0.0)
        self.assertEqual(report["metrics"]["precision"], 0.0)
        self.assertEqual(report["metrics"]["recall"], 0.0)
        self.assertEqual(report["metrics"]["detection_recall"], 1.0)
        self.assertAlmostEqual(report["metrics"]["attribute_accuracy"], 1 / 3, places=4)
        self.assertEqual(report["counts"]["missed_differences"], 1)
        self.assertEqual(report["counts"]["extra_predictions"], 1)

    def test_reversed_change_scores_zero_even_with_high_word_overlap(self):
        expected = {"kind": "count_change", "subject": "birds", "attribute": "number", "from": "two small red birds", "to": "three small red birds"}
        predicted = dict(expected, **{"from": expected["to"], "to": expected["from"]})
        report = self._evaluate_single_item([expected], [predicted])
        self.assertEqual(report["metrics"]["overall_score"], 0.0)
        self.assertEqual(report["counts"]["detected_differences"], 1)

    def test_missing_required_details_do_not_count_as_correct(self):
        expected = {"kind": "attribute_change", "subject": "shirt", "attribute": "color", "from": "red", "to": "blue"}
        predicted = {"kind": "attribute_change", "subject": "shirt"}
        report = self._evaluate_single_item([expected], [predicted])
        self.assertEqual(report["metrics"]["overall_score"], 0.0)
        self.assertEqual(report["counts"]["correct_differences"], 0)

    def test_wrong_required_count_does_not_count_as_correct(self):
        expected = {"kind": "object_added", "subject": "flower", "count": 4}
        report = self._evaluate_single_item([expected], [dict(expected, count=3)])
        self.assertEqual(report["metrics"]["overall_score"], 0.0)
        self.assertEqual(report["counts"]["detected_differences"], 1)

    def test_duplicate_spam_has_low_f1(self):
        value = self._perfect_predictions()
        for item in value["items"]:
            item["differences"] *= 100
        directory, path = self._write_predictions(value)
        try:
            report = evaluate_manifest(ROOT / "data/manifest.json", path)
        finally:
            directory.cleanup()
        self.assertEqual(report["counts"]["correct_differences"], 61)
        self.assertEqual(report["counts"]["extra_predictions"], 6039)
        self.assertEqual(report["metrics"]["precision"], 0.01)
        self.assertEqual(report["metrics"]["overall_score"], 0.0198)

    def test_partial_prediction_does_not_block_a_complete_prediction(self):
        expected = {"kind": "attribute_change", "subject": "shirt", "attribute": "color", "from": "red", "to": "blue"}
        partial = dict(expected, **{"to": "green"})
        for predictions in ([partial, expected], [expected, partial]):
            with self.subTest(predictions=predictions):
                report = self._evaluate_single_item([expected], predictions)
                self.assertEqual(report["counts"]["correct_differences"], 1)
                self.assertEqual(report["counts"]["extra_predictions"], 1)
                self.assertEqual(report["metrics"]["overall_score"], 0.6667)
                self.assertEqual(report["items"][0]["matched"][0]["prediction_index"], predictions.index(expected))

    def test_no_change_correct_abstention_scores_one(self):
        report = self._evaluate_single_item([], [])
        self.assertEqual(report["metrics"]["overall_score"], 1.0)
        self.assertEqual(report["items"][0]["metrics"]["overall_score"], 1.0)

    def test_no_change_hallucination_scores_zero(self):
        report = self._evaluate_single_item([], [{"kind": "object_added", "subject": "cloud"}])
        self.assertEqual(report["metrics"]["overall_score"], 0.0)
        self.assertEqual(report["items"][0]["metrics"]["overall_score"], 0.0)

    def test_unknown_item_predictions_reduce_precision_and_f1(self):
        expected = {"kind": "object_added", "subject": "cloud"}
        report = self._evaluate_single_item([expected], [expected], [
            {"item_id": "unknown", "differences": [expected]}
        ])
        self.assertEqual(report["metrics"]["precision"], 0.5)
        self.assertEqual(report["metrics"]["overall_score"], 0.6667)
        self.assertEqual(report["counts"]["extra_predictions"], 1)

    def test_opposite_subject_locations_cannot_match(self):
        expected = {"kind": "object_removed", "subject": "bottom_left_sprinkle"}
        report = self._evaluate_single_item([expected], [dict(expected, subject="bottom_right_sprinkle")])
        self.assertEqual(report["counts"]["correct_differences"], 0)
        self.assertEqual(report["counts"]["detected_differences"], 0)

    def test_negation_and_relation_order_are_not_ignored(self):
        for expected_value, predicted_value in [
            ("visible in front of the building", "not visible in front of the building"),
            ("red above blue", "blue above red"),
            ("paint on the box", "paint in the box"),
            ("one", "two"),
        ]:
            with self.subTest(expected_value=expected_value, predicted_value=predicted_value):
                expected = {"kind": "attribute_change", "subject": "sign", "attribute": "appearance", "from": "plain", "to": expected_value}
                report = self._evaluate_single_item([expected], [dict(expected, **{"to": predicted_value})])
                self.assertEqual(report["metrics"]["overall_score"], 0.0)

    def test_basic_field_formatting_is_still_normalized(self):
        expected = {"kind": "attribute_change", "subject": "boy_shirt", "attribute": "shirt_design", "from": "star", "to": "horizontal stripes"}
        predicted = {"kind": "attribute_change", "subject": "Boy shirt", "attribute": "Shirt design", "from": "a star", "to": "Horizontal_Stripes"}
        report = self._evaluate_single_item([expected], [predicted])
        self.assertEqual(report["metrics"]["overall_score"], 1.0)

    def test_matching_maximizes_correct_count_instead_of_greedy_overlap(self):
        expected = [Difference.from_dict({"kind": "object_added", "subject": subject}) for subject in ("gold_a", "gold_b")]
        predicted = [Difference.from_dict({"kind": "object_added", "subject": subject}) for subject in ("prediction_a", "prediction_b")]
        scores = {("prediction_a", "gold_a"): 0.9, ("prediction_a", "gold_b"): 0.8, ("prediction_b", "gold_a"): 0.85}
        with patch("spotdiff_eval.scorer._candidate_score", side_effect=lambda p, g: scores.get((p.subject, g.subject))):
            for predictions in (predicted, list(reversed(predicted))):
                matches, missed, extra = match_differences(predictions, expected, require_full_attributes=True)
                self.assertEqual(len(matches), 2)
                self.assertEqual(missed, [])
                self.assertEqual(extra, [])

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
        self.assertEqual(report["metrics"]["overall_score"], 0.0635)


def load_predictions_from_value(value):
    from spotdiff_eval.schema import PredictionDocument

    return PredictionDocument.from_dict(value)


if __name__ == "__main__":
    unittest.main()
