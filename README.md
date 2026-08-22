# SpotDiff Eval

SpotDiff Eval is a deterministic evaluator for visual spot-the-difference benchmarks. Each item is one composite image containing two panels. A model identifies the differences and returns structured JSON; the evaluator compares that output with the approved golden annotations.

The official score does not require an LLM judge or a model provider account.

## Install

From this repository:

```bash
pip install -e .
```

## Prediction format

The complete schema is in [`schemas/prediction.schema.json`](schemas/prediction.schema.json). A prediction file has one entry per image:

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

`description` is optional. The evaluator matches structured fields deterministically and tolerates basic formatting differences such as capitalization, punctuation, and singular/plural forms.

## Run the evaluator

Use the included example:

```bash
spotdiff evaluate \
  --manifest data/manifest.json \
  --predictions predictions/example.json \
  --output results/example.json
```

The terminal output includes the overall score and per-image results. The optional `--output` flag writes the complete machine-readable report.

The repository also includes a complete approved baseline:

```bash
spotdiff evaluate \
  --manifest data/manifest.json \
  --predictions predictions/perfect.json
```

This should report 100% for all metrics. It is a regression fixture for the
approved annotations and scorer.

You can also run it without installing the package:

```bash
python -m spotdiff_eval.cli evaluate \
  --manifest data/manifest.json \
  --predictions predictions/example.json
```

## Scoring

The official weighted score is:

```text
overall_score =
    0.60 * recall
  + 0.25 * precision
  + 0.15 * attribute_accuracy
```

- Recall measures how many golden differences were found.
- Precision measures how many model predictions were correct rather than extra.
- Attribute accuracy measures whether matched changes have the correct attribute and before/after values.

Matching is one-to-one and deterministic. Object additions/removals are matched by difference kind and subject. Attribute/count changes also compare the attribute and before/after fields for the attribute sub-score.

## Any model can be used

SpotDiff does not call or restrict the model. Run any vision model—hosted or local—on the complete composite images in `data/images/`, convert its answers to the prediction format, and pass the resulting JSON to `spotdiff evaluate`.

## Optional endpoint runner

The evaluator does not require a model endpoint. For convenience, `spotdiff run`
can call an OpenAI-compatible chat-completions-style vision endpoint and write
the standard predictions file. The API token is read from an environment
variable and is never written to the output.

```bash
export SPOTDIFF_API_TOKEN="your-token"

spotdiff run \
  --endpoint https://your-provider.example/v1/chat/completions \
  --model your-vision-model \
  --manifest data/manifest.json \
  --output predictions/my-model.json

spotdiff evaluate \
  --manifest data/manifest.json \
  --predictions predictions/my-model.json
```

For a custom endpoint accepting a simple JSON body with `prompt`, `image`, and
optional `model`, use:

```bash
spotdiff run \
  --protocol generic_json \
  --endpoint https://your-provider.example/vision \
  --token-env MY_API_TOKEN \
  --manifest data/manifest.json \
  --output predictions/my-model.json
```

Use `--limit 1` to test one image before running the full dataset. The runner
sends each complete composite image as a base64 data URL; it does not split the
image into separate image A and image B files.

The scorer uses a deterministic lexical similarity threshold for matching. Very
weak subject matches are treated as extra predictions rather than being counted
as correct. This avoids rewarding unrelated descriptions that happen to share
one generic word.
