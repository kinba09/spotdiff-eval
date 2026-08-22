"""Validation and loading for SpotDiff prediction and annotation JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


class SchemaError(ValueError):
    """Raised when a prediction or annotation does not follow the schema."""


ALLOWED_KINDS = {
    "object_added",
    "object_removed",
    "attribute_change",
    "count_change",
}


def _required_string(value: Any, field: str, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{context}: '{field}' must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class Difference:
    kind: str
    subject: str
    attribute: Optional[str] = None
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    count: Optional[int] = None
    description: Optional[str] = None
    identifier: Optional[str] = None

    @classmethod
    def from_dict(cls, value: Any, context: str = "difference") -> "Difference":
        if not isinstance(value, dict):
            raise SchemaError(f"{context}: each difference must be an object")

        kind = _required_string(value.get("kind"), "kind", context)
        if kind not in ALLOWED_KINDS:
            allowed = ", ".join(sorted(ALLOWED_KINDS))
            raise SchemaError(f"{context}: unsupported kind '{kind}'; use one of {allowed}")

        subject = _required_string(value.get("subject"), "subject", context)

        optional_strings: Dict[str, Optional[str]] = {}
        for json_name in ("attribute", "from", "to", "description"):
            raw = value.get(json_name)
            if raw is not None and (not isinstance(raw, str) or not raw.strip()):
                raise SchemaError(f"{context}: '{json_name}' must be a non-empty string when provided")
            optional_strings[json_name] = raw.strip() if isinstance(raw, str) else None

        count = value.get("count")
        if count is not None and (not isinstance(count, int) or isinstance(count, bool) or count < 1):
            raise SchemaError(f"{context}: 'count' must be a positive integer when provided")

        identifier = value.get("id")
        if identifier is not None and (not isinstance(identifier, str) or not identifier.strip()):
            raise SchemaError(f"{context}: 'id' must be a non-empty string when provided")

        return cls(
            kind=kind,
            subject=subject,
            attribute=optional_strings["attribute"],
            from_value=optional_strings["from"],
            to_value=optional_strings["to"],
            count=count,
            description=optional_strings["description"],
            identifier=identifier.strip() if isinstance(identifier, str) else None,
        )

    def to_dict(self, include_id: bool = False) -> Dict[str, Any]:
        result: Dict[str, Any] = {"kind": self.kind, "subject": self.subject}
        if self.attribute is not None:
            result["attribute"] = self.attribute
        if self.from_value is not None:
            result["from"] = self.from_value
        if self.to_value is not None:
            result["to"] = self.to_value
        if self.count is not None:
            result["count"] = self.count
        if self.description is not None:
            result["description"] = self.description
        if include_id and self.identifier is not None:
            result["id"] = self.identifier
        return result


@dataclass(frozen=True)
class PredictionItem:
    item_id: str
    differences: List[Difference]

    @classmethod
    def from_dict(cls, value: Any, index: int) -> "PredictionItem":
        context = f"items[{index}]"
        if not isinstance(value, dict):
            raise SchemaError(f"{context}: each item must be an object")
        item_id = _required_string(value.get("item_id"), "item_id", context)
        differences = value.get("differences", [])
        if not isinstance(differences, list):
            raise SchemaError(f"{context}: 'differences' must be an array")
        parsed = [Difference.from_dict(difference, f"{context}.differences[{i}]") for i, difference in enumerate(differences)]
        return cls(item_id=item_id, differences=parsed)


@dataclass(frozen=True)
class PredictionDocument:
    schema_version: str
    model: Optional[str]
    items: List[PredictionItem]

    @classmethod
    def from_dict(cls, value: Any) -> "PredictionDocument":
        if not isinstance(value, dict):
            raise SchemaError("prediction file must contain a JSON object")

        version = _required_string(value.get("schema_version"), "schema_version", "root")
        if version != "1.0":
            raise SchemaError(f"root: unsupported schema_version '{version}'; expected '1.0'")

        model = value.get("model")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise SchemaError("root: 'model' must be a non-empty string when provided")

        items = value.get("items")
        if not isinstance(items, list):
            raise SchemaError("root: 'items' must be an array")

        parsed_items = [PredictionItem.from_dict(item, index) for index, item in enumerate(items)]
        seen_ids = set()
        for item in parsed_items:
            if item.item_id in seen_ids:
                raise SchemaError(f"root: duplicate item_id '{item.item_id}'")
            seen_ids.add(item.item_id)

        return cls(
            schema_version=version,
            model=model.strip() if isinstance(model, str) else None,
            items=parsed_items,
        )


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise SchemaError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SchemaError(f"invalid JSON in {path}: {exc.msg} at line {exc.lineno}, column {exc.colno}") from exc


def load_predictions(path: Path) -> PredictionDocument:
    return PredictionDocument.from_dict(load_json(path))


def load_annotation_differences(path: Path) -> List[Difference]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise SchemaError(f"annotation file {path} must contain a JSON object")
    raw_differences = value.get("differences")
    if not isinstance(raw_differences, list):
        raise SchemaError(f"annotation file {path}: 'differences' must be an array")
    return [Difference.from_dict(difference, f"{path}.differences[{i}]") for i, difference in enumerate(raw_differences)]
