"""Deterministic matching and strict F1 scoring for SpotDiff predictions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from . import __version__
from .schema import Difference, PredictionItem, load_annotation_differences, load_json, load_predictions


MATCH_THRESHOLD = 0.40

_STOP_WORDS = {
    "a", "an", "and", "are", "at", "be", "by", "from", "in", "is", "near", "of", "on",
    "the", "to", "with", "panel", "area", "side",
}
_FIELD_STOP_WORDS = {"a", "an", "the", "and"}


def _token_sequence(value: Optional[str], stop_words: Set[str] = _STOP_WORDS) -> Tuple[str, ...]:
    if not value:
        return ()
    raw_tokens = re.findall(r"[a-z0-9]+", value.lower().replace("&", " and "))
    normalized = []
    for token in raw_tokens:
        if token in stop_words:
            continue
        if token.endswith("ies") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("s") and not token.endswith("ss") and len(token) > 3:
            token = token[:-1]
        normalized.append(token)
    return tuple(normalized)


def _tokens(value: Optional[str]) -> Set[str]:
    return set(_token_sequence(value))


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
    # Required details must agree after basic formatting/plural normalization.
    # Fuzzy overlap can accept negation, reversed relations, or wrong numbers.
    expected_tokens = _token_sequence(expected, _FIELD_STOP_WORDS)
    return bool(expected_tokens) and _token_sequence(predicted, _FIELD_STOP_WORDS) == expected_tokens


def _candidate_score(predicted: Difference, expected: Difference) -> Optional[float]:
    if predicted.kind != expected.kind:
        return None

    predicted_tokens = _tokens(predicted.subject)
    expected_tokens = _tokens(expected.subject)
    for opposites in ({"left", "right"}, {"top", "bottom"}, {"upper", "lower"}):
        predicted_location = predicted_tokens & opposites
        expected_location = expected_tokens & opposites
        if predicted_location and expected_location and predicted_location.isdisjoint(expected_location):
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


def match_differences(
    predicted: Sequence[Difference],
    expected: Sequence[Difference],
    *,
    require_full_attributes: bool = False,
) -> Tuple[List[Match], List[int], List[int]]:
    """Maximize eligible one-to-one matches; partial matches are diagnostic only."""
    candidates: Dict[int, List[Match]] = {}
    for predicted_index, predicted_difference in enumerate(predicted):
        for expected_index, expected_difference in enumerate(expected):
            score = _candidate_score(predicted_difference, expected_difference)
            if score is not None and score >= MATCH_THRESHOLD:
                accuracy = _attribute_accuracy(predicted_difference, expected_difference)
                if require_full_attributes and accuracy != 1.0:
                    continue
                candidates.setdefault(predicted_index, []).append(
                    Match(predicted_index, expected_index, score, accuracy)
                )

    for choices in candidates.values():
        choices.sort(key=lambda match: (-match.match_score, match.expected_index))

    # Augmenting paths maximize match count, which is the strict F1 objective.
    # A single high-overlap candidate must not block two valid matches.
    assigned: Dict[int, Match] = {}

    def assign(predicted_index: int, visited: Set[int]) -> bool:
        for candidate in candidates.get(predicted_index, []):
            expected_index = candidate.expected_index
            if expected_index in visited:
                continue
            visited.add(expected_index)
            previous = assigned.get(expected_index)
            if previous is None or assign(previous.predicted_index, visited):
                assigned[expected_index] = candidate
                return True
        return False

    for predicted_index in sorted(candidates, key=lambda index: (-candidates[index][0].match_score, index)):
        assign(predicted_index, set())

    matches = list(assigned.values())
    matches.sort(key=lambda match: match.expected_index)
    used_predicted = {match.predicted_index for match in matches}
    used_expected = set(assigned)
    missed = [index for index in range(len(expected)) if index not in used_expected]
    extra = [index for index in range(len(predicted)) if index not in used_predicted]
    return matches, missed, extra


def _safe_ratio(numerator: float, denominator: float, empty_value: float = 0.0) -> float:
    return numerator / denominator if denominator else empty_value


def _metrics(correct: int, gold: int, predicted: int, detected: int, attribute_sum: float) -> Dict[str, float]:
    recall = _safe_ratio(correct, gold, empty_value=1.0)
    precision = _safe_ratio(correct, predicted, empty_value=1.0 if not gold else 0.0)
    f1 = _safe_ratio(2 * correct, gold + predicted, empty_value=1.0)
    return {
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "f1": round(f1, 4),
        "overall_score": round(f1, 4),
        "difference_coverage": round(recall, 4),
        "detection_recall": round(_safe_ratio(detected, gold, empty_value=1.0), 4),
        "detection_precision": round(_safe_ratio(detected, predicted, empty_value=1.0 if not gold else 0.0), 4),
        "attribute_accuracy": round(_safe_ratio(attribute_sum, detected), 4),
    }


def _match_report(match: Match, expected: Sequence[Difference]) -> Dict[str, Any]:
    return {
        "prediction_index": match.predicted_index,
        "gold_id": expected[match.expected_index].identifier,
        "gold_index": match.expected_index,
        "match_score": round(match.match_score, 4),
        "attribute_accuracy": match.attribute_accuracy,
    }


def _item_score(item_id: str, expected: Sequence[Difference], predicted: Sequence[Difference]) -> Dict[str, Any]:
    matches, missed_indices, extra_indices = match_differences(predicted, expected, require_full_attributes=True)
    detections, _, _ = match_differences(predicted, expected)
    true_positives = len(matches)

    return {
        "item_id": item_id,
        "metrics": _metrics(
            true_positives, len(expected), len(predicted), len(detections),
            sum(match.attribute_accuracy for match in detections),
        ),
        "counts": {
            "gold_differences": len(expected),
            "predicted_differences": len(predicted),
            "correct_differences": true_positives,
            "exact_correct_differences": true_positives,
            "detected_differences": len(detections),
            "missed_differences": len(missed_indices),
            "extra_predictions": len(extra_indices),
        },
        "matched": [_match_report(match, expected) for match in matches],
        "detection_matched": [_match_report(match, expected) for match in detections],
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
    detected_total = sum(report["counts"]["detected_differences"] for report in item_reports)
    predicted_total += sum(item["predicted_differences"] for item in unknown_items)
    attribute_sum = sum(
        match["attribute_accuracy"]
        for report in item_reports
        for match in report["detection_matched"]
    )

    return {
        "schema_version": "2.0",
        "evaluator_version": __version__,
        "model": predictions.model,
        "scoring_method": "strict_f1",
        "metrics": _metrics(matched_total, gold_total, predicted_total, detected_total, attribute_sum),
        "counts": {
            "items": len(item_reports),
            "gold_differences": gold_total,
            "predicted_differences": predicted_total,
            "correct_differences": matched_total,
            "exact_correct_differences": matched_total,
            "detected_differences": detected_total,
            "missed_differences": gold_total - matched_total,
            "extra_predictions": predicted_total - matched_total,
        },
        "items": item_reports,
        "unknown_prediction_items": unknown_items,
    }


def write_report(report: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
