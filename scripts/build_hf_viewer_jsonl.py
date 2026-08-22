"""Build the uniform JSONL file used by the Hugging Face Dataset Viewer."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data/manifest.json"
OUTPUT_PATH = ROOT / "data/viewer/spotdiff_v1_dev.jsonl"


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    rows = []
    for item in manifest["items"]:
        annotation_path = ROOT / item["annotation"]
        annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
        for difference in annotation["differences"]:
            rows.append(
                {
                    "item_id": item["item_id"],
                    "image": item["image"],
                    "panel_layout": item["panel_layout"],
                    "difference_id": difference["id"],
                    "kind": difference["kind"],
                    "subject": difference["subject"],
                    "attribute": difference.get("attribute", ""),
                    "from": difference.get("from", ""),
                    "to": difference.get("to", ""),
                    "count": difference.get("count"),
                    "description": difference.get("description", ""),
                    "confidence": difference.get("confidence", ""),
                }
            )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
