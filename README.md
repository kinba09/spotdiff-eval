# SpotDiff Eval

SpotDiff Eval is an open, reproducible benchmark for visual spot-the-difference
tasks. Each item is one composite image containing two nearly identical panels.
A model receives the complete image and returns every visible difference as
structured JSON. Bounding boxes and coordinates are not required in v1.

The `spotdiff-v1-dev` release is intentionally public: images, annotations,
and the deterministic evaluator are available for local inspection and
reproduction. Community leaderboard results are self-reported. A future hidden
test split can support an independently verified leaderboard.

## Install

From GitHub:

```bash
git clone https://github.com/kinba09/spotdiff-eval.git
cd spotdiff-eval
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Or install the package from a local checkout with:

```bash
python -m pip install -e .
```

## Download the development dataset

The public development dataset is also available on Hugging Face:
`Abnik/spotdiff-v1-dev`.

In an empty working directory, run:

```bash
spotdiff download --dataset Abnik/spotdiff-v1-dev
```

The command preserves the repository paths, so the downloaded manifest is:
`data/manifest.json`.

Use `--output` to choose another destination or `--revision` to pin a dataset
branch, tag, or commit:

```bash
spotdiff download \
  --dataset Abnik/spotdiff-v1-dev \
  --revision main \
  --output ./spotdiff-data
```

## Run any model

SpotDiff does not restrict the model provider. Use any hosted or local vision
model on the complete composite images in `data/images/`. The model should
write one standard predictions file:

```json
{
  "schema_version": "1.0",
  "model": "my-vision-model",
  "items": [
    {
      "item_id": "scene_0001_playground",
      "differences": [
        {
          "kind": "object_removed",
          "subject": "playground_flag"
        },
        {
          "kind": "attribute_change",
          "subject": "boy_shirt",
          "attribute": "shirt_design",
          "from": "star",
          "to": "horizontal stripes"
        }
      ]
    }
  ]
}
```

The complete schema is in [`schemas/prediction.schema.json`](schemas/prediction.schema.json).
`description` is optional. Models may use their own internal names; the scorer
normalizes basic formatting differences and performs deterministic matching.

## Evaluate predictions

```bash
spotdiff evaluate \
  --manifest data/manifest.json \
  --predictions predictions/your-model.json \
  --output results/your-model.json
```

The command prints the final score, coverage, recall, precision, attribute
accuracy, per-image results, missed differences, and extra predictions. The
JSON report contains the complete machine-readable details.

The repository includes a complete approved baseline:

```bash
spotdiff evaluate \
  --manifest data/manifest.json \
  --predictions predictions/perfect.json
```

It should score 100% and acts as a regression fixture for the annotations and
scorer.

Without installing the console script, use:

```bash
python3 -m spotdiff_eval.cli evaluate \
  --manifest data/manifest.json \
  --predictions predictions/example.json
```

## Metrics

The official development score is deterministic:

```text
overall_score =
    0.60 * recall
  + 0.25 * precision
  + 0.15 * attribute_accuracy
```

- Recall measures how many golden differences were detected.
- Precision measures how many model predictions were correct rather than extra.
- Attribute accuracy measures whether matched changes have the correct details.
- Difference coverage measures the fraction of golden differences that were
  matched with fully correct structured attributes. It is reported separately
  and does not change the official weighted score.

Matching is one-to-one and deterministic. Weak subject matches are treated as
extra predictions rather than being counted as correct.

## Optional endpoint runner

For convenience, the package can call an OpenAI-compatible vision endpoint. It
sends each complete composite image as a base64 data URL; it does not split the
image into separate files.

```bash
export SPOTDIFF_API_TOKEN="your-token"

spotdiff run \
  --endpoint https://your-provider.example/v1/chat/completions \
  --model your-vision-model \
  --manifest data/manifest.json \
  --output predictions/my-model.json
```

Use `--limit 1` to test one image before running the full dataset. The API
token is read from an environment variable and is never written to output.

The built-in prompt is maintained separately at
`spotdiff_eval/prompts/spotdiff_v1.txt`. Override it for experiments with:

```bash
spotdiff run \
  --endpoint https://your-provider.example/v1/chat/completions \
  --model your-vision-model \
  --prompt-file prompts/my-spotdiff-prompt.txt \
  --manifest data/manifest.json \
  --output predictions/my-model.json
```

## Community leaderboard

See [`LEADERBOARD.md`](LEADERBOARD.md) for the self-reported development
leaderboard and submission instructions.

## Dataset and image rights

The dataset card is in [`data/README.md`](data/README.md). Before public
distribution, the maintainer must confirm that the source images may be
redistributed and document their provenance and license.
