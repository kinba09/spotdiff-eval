"""Optional model runner for OpenAI-compatible and simple JSON vision APIs.

The evaluator itself remains provider-independent. This module only turns a
model endpoint's responses into the standard SpotDiff prediction format.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .schema import PredictionItem, load_json
from .scorer import _resolve_path


DEFAULT_PROMPT = """You are solving a visual spot-the-difference task.
The input is one complete composite image containing two panels. Identify every difference between the panels.
Return JSON only, with this exact shape:
{
  \"differences\": [
    {
      \"kind\": \"object_added|object_removed|attribute_change|count_change\",
      \"subject\": \"short concise subject name\",
      \"attribute\": \"optional attribute name\",
      \"from\": \"optional left/top-panel value\",
      \"to\": \"optional right/bottom-panel value\"
    }
  ]
}
Do not include coordinates or bounding boxes. Do not include explanations outside the JSON object."""


class RunError(RuntimeError):
    """Raised when a model endpoint cannot be called or parsed."""


def image_as_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_request_payload(
    image_data_url: str,
    prompt: str,
    model: Optional[str],
    protocol: str,
) -> Dict[str, Any]:
    if protocol == "openai_compatible":
        payload: Dict[str, Any] = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                }
            ],
            "temperature": 0,
        }
        if model:
            payload["model"] = model
        return payload

    if protocol == "generic_json":
        payload = {"prompt": prompt, "image": image_data_url}
        if model:
            payload["model"] = model
        return payload

    raise RunError(f"unsupported protocol '{protocol}'")


def call_endpoint(
    endpoint: str,
    payload: Dict[str, Any],
    token: Optional[str] = None,
    token_header: str = "Authorization",
    token_prefix: str = "Bearer",
    timeout: int = 120,
) -> Any:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers[token_header] = f"{token_prefix} {token}".strip()

    request = Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RunError(f"model endpoint returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RunError(f"could not reach model endpoint: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RunError(f"model endpoint timed out after {timeout} seconds") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RunError("model endpoint returned a non-JSON response") from exc


def _json_from_text(value: str) -> Any:
    text = value.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RunError("model response did not contain valid JSON") from exc


def _content_to_text(content: Any) -> Optional[str]:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "\n".join(parts) if parts else None
    return None


def extract_prediction_object(response: Any) -> Dict[str, Any]:
    """Extract a SpotDiff object from common endpoint response envelopes."""
    if isinstance(response, list):
        return {"differences": response}
    if not isinstance(response, dict):
        raise RunError("model response must be a JSON object or array")
    if isinstance(response.get("differences"), list):
        return response

    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0]
        if isinstance(choice, dict):
            message = choice.get("message")
            content = message.get("content") if isinstance(message, dict) else choice.get("text")
            text = _content_to_text(content)
            if text is not None:
                return extract_prediction_object(_json_from_text(text))

    for key in ("output_text", "text", "output", "content"):
        text = _content_to_text(response.get(key))
        if text is not None:
            return extract_prediction_object(_json_from_text(text))

    items = response.get("items")
    if isinstance(items, list) and len(items) == 1 and isinstance(items[0], dict):
        return extract_prediction_object(items[0])

    raise RunError("could not find a 'differences' array in the model response")


def run_manifest(
    manifest_path: Path,
    endpoint: str,
    model: Optional[str] = None,
    token: Optional[str] = None,
    protocol: str = "openai_compatible",
    prompt: str = DEFAULT_PROMPT,
    token_header: str = "Authorization",
    token_prefix: str = "Bearer",
    timeout: int = 120,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("items"), list):
        raise RunError(f"manifest {manifest_path}: expected an object with an 'items' array")

    raw_items = manifest["items"][:limit] if limit is not None else manifest["items"]
    output_items: List[Dict[str, Any]] = []
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict) or not isinstance(raw_item.get("item_id"), str):
            raise RunError(f"manifest item {index}: missing item_id")
        image_value = raw_item.get("image")
        if not isinstance(image_value, str):
            raise RunError(f"manifest item {index}: missing image")
        image_path = _resolve_path(manifest_path.parent, image_value)
        if not image_path.exists():
            raise RunError(f"image not found for {raw_item['item_id']}: {image_path}")

        payload = build_request_payload(image_as_data_url(image_path), prompt, model, protocol)
        response = call_endpoint(
            endpoint,
            payload,
            token=token,
            token_header=token_header,
            token_prefix=token_prefix,
            timeout=timeout,
        )
        response_object = extract_prediction_object(response)
        prediction_item = PredictionItem.from_dict(
            {"item_id": raw_item["item_id"], "differences": response_object["differences"]},
            index,
        )
        output_items.append(
            {
                "item_id": prediction_item.item_id,
                "differences": [difference.to_dict() for difference in prediction_item.differences],
            }
        )

    return {"schema_version": "1.0", "model": model or endpoint, "items": output_items}


def write_predictions(predictions: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(predictions, handle, indent=2)
        handle.write("\n")
