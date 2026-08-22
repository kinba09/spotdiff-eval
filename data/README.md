---
pretty_name: SpotDiff v1 Development
tags:
- visual-reasoning
- spot-the-difference
- image-to-text
size_categories:
- n<1K
task_categories:
- image-to-text
license: other
---

# SpotDiff v1 Development Dataset

SpotDiff is a visual spot-the-difference benchmark. Each item is one composite
image containing two nearly identical panels. A model receives the complete
image and identifies every visible difference using structured JSON.

This is the public development release. It contains 10 reviewed images and 61
gold differences. The annotations are intentionally public so that anyone can
reproduce the evaluator locally and inspect the benchmark design.

## Layout

- `images/`: composite images with both panels
- `annotations/`: approved golden structured differences
- `manifest.json`: item IDs, image paths, and annotation paths
- `dataset_version.json`: release metadata

## Evaluation

Install the evaluator from GitHub, or run it from a checkout:

```bash
pip install -e .
spotdiff evaluate \
  --manifest data/manifest.json \
  --predictions predictions/your-model.json
```

The official development score is deterministic:

```text
0.60 * recall + 0.25 * precision + 0.15 * attribute_accuracy
```

Because this is a development benchmark, the answers are public and results
are suitable for reproducibility and community-reported comparisons. They are
not a hidden-test leaderboard result.

## Image rights

Before publishing this dataset, the dataset maintainer must confirm that the
source images may be redistributed. The `other` license marker is deliberate
until the image provenance and license are documented.
