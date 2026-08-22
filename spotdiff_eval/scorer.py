"""Deterministic matching and weighted scoring for SpotDiff predictions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .schema import Difference, PredictionItem, load_annotation_differences, load_json, load_predictions


WEIGHTS = {
    "recall": 0.60,
    "precision": 0.25,
    "attribute_accuracy": 0.15,
}
MATCH_THRESHOLD = 0.40

_STOP_WORDS = {
    "a", "an", "and", "are", "at", "be", "by", "from", "in", "is", "near", "of", "on",
    "one", "the", "to", "with", "left", "right", "panel", "area", "side",
}


def _tokens(value: Optional[str]) -> Set[str]:
    if not value:
        return set()
    raw_tokens = re.findall(r"[a-z0-9]+", value.lower().replace("&", " and "))
    normalized = set()
    for token in raw_tokens:
        if token in _STOP_WORDS:
            continue
        if token.endswith("ies") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("s") and not token.endswith("ss") and len(token) > 3:
            token = token[:-1]
        normalized.add(token)
    return normalized


def _similarity(left: Optional[str], right: Optional[str]) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    if left_tokens == right_tokens:
        return 1.0
    overlap = len(left_tokens & right_tokens)
    return (2.0 * overlap) / (len(left_tokens) + len(right_tokens))


def _field_correct(predicted: Optional[str], expected: Optional[str]) -> bool:
    if expected is None:
        return True
    return _similarity(predicted, expected) >= 0.80


def _candidate_score(predicted: Difference, expected: Difference) -> Optional[float]:
    if predicted.kind != expected.kind:
        return None

    subject_score = _similarity(predicted.subject, expected.subject)
    description_score = _similarity(predicted.description, expected.description)
    if subject_score < 0.45 and description_score < 0.45:
        return None

    if predicted.kind in {"object_added", "object_removed"}:
        score = 0.80 * subject_score + 0.20 * description_score
        if subject_score < 0.50 and description_score < 0.65:
            return None
        return score

    attribute_score = _similarity(predicted.attribute, expected.attribute)
    from_score = _similarity(predicted.from_value, expected.from_value)
    to_score = _similarity(predicted.to_value, expected.to_value)
    score = (
        0.55 * subject_score
        + 0.20 * attribute_score
        + 0.125 * from_score
        + 0.125 * to_score
    )
    if subject_score < 0.50 and score < 0.60:
        return None
    return score


def _attribute_accuracy(predicted: Difference, expected: Difference) -> float:
    if expected.kind in {"object_added", "object_removed"}:
        if expected.count is not None:
            return 1.0 if predicted.count == expected.count else 0.0
        return 1.0

    checks = [
        _field_correct(predicted.attribute, expected.attribute),
        _field_correct(predicted.from_value, expected.from_value),
        _field_correct(predicted.to_value, expected.to_value),
    ]
    if expected.count is not None:
        checks.append(predicted.count == expected.count)
    return sum(checks) / len(checks) if checks else 1.0


@dataclass(frozen=True)
class Match:
    predicted_index: int
    expected_index: int
    match_score: float
    attribute_accuracy: float


def match_differences(predicted: Sequence[Difference], expected: Sequence[Difference]) -> Tuple[List[Match], List[int], List[int]]:
    candidates: List[Tuple[float, int, int]] = []
    for predicted_index, predicted_difference in enumerate(predicted):
        for expected_index, expected_difference in enumerate(expected):
            score = _candidate_score(predicted_difference, expected_difference)
            if score is not None and score >= MATCH_THRESHOLD:
                candidates.append((score, predicted_index, expected_index))

    # Greedy maximum-weight one-to-one matching is deterministic for this small benchmark.
    candidates.sort(key=lambda candidate: (-candidate[0], candidate[1], candidate[2]))
    used_predicted: Set[int] = set()
    used_expected: Set[int] = set()
    matches: List[Match] = []
    for score, predicted_index, expected_index in candidates:
        if predicted_index in used_predicted or expected_index in used_expected:
            continue
        used_predicted.add(predicted_index)
        used_expected.add(expected_index)
        matches.append(
            Match(
                predicted_index=predicted_index,
                expected_index=expected_index,
                match_score=round(score, 4),
                attribute_accuracy=round(_attribute_accuracy(predicted[predicted_index], expected[expected_index]), 4),
            )
        )

    matches.sort(key=lambda match: match.expected_index)
    missed = [index for index in range(len(expected)) if index not in used_expected]
    extra = [index for index in range(len(predicted)) if index not in used_predicted]
    return matches, missed, extra


def _safe_ratio(numerator: float, denominator: float, empty_value: float = 0.0) -> float:
    return numerator / denominator if denominator else empty_value


def _item_score(item_id: str, expected: Sequence[Difference], predicted: Sequence[Difference]) -> Dict[str, Any]:
    matches, missed_indices, extra_indices = match_differences(predicted, expected)
    true_positives = len(matches)
    recall = _safe_ratio(true_positives, len(expected), empty_value=1.0)
    precision = _safe_ratio(true_positives, len(predicted), empty_value=1.0 if not expected else 0.0)
    attribute_accuracy = _safe_ratio(
        sum(match.attribute_accuracy for match in matches),
        len(matches),
        empty_value=0.0,
    )
    overall = (
        WEIGHTS["recall"] * recall
        + WEIGHTS["precision"] * precision
        + WEIGHTS["attribute_accuracy"] * attribute_accuracy
    )

    return {
        "item_id": item_id,
        "metrics": {
            "recall": round(recall, 4),
            "precision": round(precision, 4),
            "attribute_accuracy": round(attribute_accuracy, 4),
            "overall_score": round(overall, 4),
        },
        "counts": {
            "gold_differences": len(expected),
            "predicted_differences": len(predicted),
            "correct_differences": true_positives,
            "missed_differences": len(missed_indices),
            "extra_predictions": len(extra_indices),
        },
        "matched": [
            {
                "prediction_index": match.predicted_index,
                "gold_id": expected[match.expected_index].identifier,
                "gold_index": match.expected_index,
                "match_score": match.match_score,
                "attribute_accuracy": match.attribute_accuracy,
            }
            for match in matches
        ],
        "missed": [expected[index].to_dict(include_id=True) for index in missed_indices],
        "extra": [predicted[index].to_dict() for index in extra_indices],
    }


def _resolve_path(base: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    # The checked-in manifest uses repository-root-relative paths such as
    # ``data/annotations/...`` even though the manifest itself lives in
    # ``data/``. Prefer the manifest directory when possible, then fall back
    # to its parent so both layouts work for local and downloaded datasets.
    manifest_relative = base / path
    if manifest_relative.exists():
        return manifest_relative
    return base.parent / path


def evaluate_manifest(manifest_path: Path, prediction_path: Path) -> Dict[str, Any]:
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("items"), list):
        raise ValueError(f"manifest {manifest_path}: expected an object with an 'items' array")

    predictions = load_predictions(prediction_path)
    prediction_by_id = {item.item_id: item for item in predictions.items}
    manifest_base = manifest_path.parent
    item_reports: List[Dict[str, Any]] = []
    known_ids: Set[str] = set()

    for raw_item in manifest["items"]:
        if not isinstance(raw_item, dict) or not isinstance(raw_item.get("item_id"), str):
            raise ValueError(f"manifest {manifest_path}: every item needs an item_id and annotation")
        item_id = raw_item["item_id"]
        annotation_value = raw_item.get("annotation")
        if not isinstance(annotation_value, str):
            raise ValueError(f"manifest {manifest_path}: item '{item_id}' is missing annotation")
        known_ids.add(item_id)
        expected = load_annotation_differences(_resolve_path(manifest_base, annotation_value))
        prediction_item: Optional[PredictionItem] = prediction_by_id.get(item_id)
        predicted = prediction_item.differences if prediction_item else []
        item_reports.append(_item_score(item_id, expected, predicted))

    unknown_items = []
    for item in predictions.items:
        if item.item_id not in known_ids:
            unknown_items.append({"item_id": item.item_id, "predicted_differences": len(item.differences)})

    gold_total = sum(report["counts"]["gold_differences"] for report in item_reports)
    predicted_total = sum(report["counts"]["predicted_differences"] for report in item_reports)
    matched_total = sum(report["counts"]["correct_differences"] for report in item_reports)
    predicted_total += sum(item["predicted_differences"] for item in unknown_items)
    attribute_sum = sum(
        report["metrics"]["attribute_accuracy"] * report["counts"]["correct_differences"]
        for report in item_reports
    )
    recall = _safe_ratio(matched_total, gold_total, empty_value=1.0)
    precision = _safe_ratio(matched_total, predicted_total, empty_value=1.0 if not gold_total else 0.0)
    attribute_accuracy = _safe_ratio(attribute_sum, matched_total)
    overall = (
        WEIGHTS["recall"] * recall
        + WEIGHTS["precision"] * precision
        + WEIGHTS["attribute_accuracy"] * attribute_accuracy
    )

    return {
        "schema_version": "1.0",
        "evaluator_version": "0.1.0",
        "model": predictions.model,
        "weights": WEIGHTS,
        "metrics": {
            "recall": round(recall, 4),
            "precision": round(precision, 4),
            "attribute_accuracy": round(attribute_accuracy, 4),
            "overall_score": round(overall, 4),
        },
        "counts": {
            "items": len(item_reports),
            "gold_differences": gold_total,
            "predicted_differences": predicted_total,
            "correct_differences": matched_total,
        },
        "items": item_reports,
        "unknown_prediction_items": unknown_items,
    }


def write_report(report: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
