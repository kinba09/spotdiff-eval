# SpotDiff Eval

SpotDiff Eval is an open, reproducible benchmark for visual spot-the-difference
tasks. Each item is one composite image containing two nearly identical panels.
A model receives the complete image and returns every visible difference as
structured JSON. Bounding boxes and coordinates are not required in v1.

The `spotdiff-v1-dev` release is intentionally public: images, annotations,
and the deterministic evaluator are available for local inspection and
reproduction. Community leaderboard results are self-reported. A future hidden
test split can support an independently verified leaderboard.

## Watch the demo

A 55-second walkthrough of the task, model answers, scoring, and community
results, with narration.

https://github.com/user-attachments/assets/4fdc06c3-1e35-409f-a4ad-8ee2ee8684cc

## Run with your coding agent

Tell your coding agent: **"Read RUN_BENCHMARK.md and run SpotDiff on
`<MODEL_NAME>`."** Replace the placeholder with the vision model you want to test.
The [agent run guide](RUN_BENCHMARK.md) covers launching the model, collecting
answers, and reporting the final score.

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

The command shows **Overall score [F1]** first as the final benchmark result,
followed by **Differences found [Recall]** and **Correct answers [Precision]**.
Additional details include partial matches and detail accuracy. Per-image
results and the JSON report provide the complete breakdown.

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

**Overall score [F1]** is the final benchmark result. It balances finding the
differences and avoiding incorrect answers. Starting with evaluator 0.3.0, it
uses complete structured matches and pools counts across images
(micro-averaging):

```text
precision = fully_correct_matches / predicted_differences
recall = fully_correct_matches / gold_differences
overall_score = f1 = 2 * fully_correct_matches / (gold_differences + predicted_differences)
```

The CLI and leaderboard use plain-language names, with metric names in brackets:

| Display name | Meaning |
| --- | --- |
| **Overall score [F1]** | The final result, balancing missed differences and incorrect answers. |
| Differences found [Recall] | The share of expected differences described completely and correctly. |
| Correct answers [Precision] | The share of reported differences that were completely correct. |
| Changes noticed [Detection recall] | The share of expected changes matched, including partial answers. |
| Relevant answers [Detection precision] | The share of reported changes matched, including partial answers. |
| Detail accuracy [Attribute accuracy] | Average correctness of structured details among diagnostic matches. |

Additional details help explain errors; they do not add points to the overall
score. All displayed percentages range from 0% to 100%, with higher being better.

- A fully correct match must identify an eligible subject and change kind, and
  match every structured detail supplied by the gold annotation: `attribute`,
  `from`, `to`, and `count` where applicable. Object additions/removals require
  their gold count when one is supplied.
- A wrong or incomplete change is both an unmatched prediction and a missed
  gold difference. Naming the right subject alone earns no strict credit.
- Duplicate and unknown-item predictions remain in the prediction denominator.
- Difference coverage is an alias of strict recall.
- `detection_recall`, `detection_precision`, and `attribute_accuracy` describe
  partial matches for diagnosis. They do not contribute to the headline score.

Matching is deterministic and one-to-one. Complete matches are selected
independently from diagnostic matches, maximizing their count so that a partial
prediction cannot block a complete one. Opposite subject locations such as
left/right are rejected. Required text fields use ordered token equality after
normalizing case, punctuation, articles, conjunctions, and simple plurals;
numbers, negation, and spatial relations remain significant.

This is a conservative text evaluator: it does not infer arbitrary synonyms or
verify pixels. Semantically equivalent wording can still be rejected; reviewed
aliases and gold localization are future matching improvements.

An image with no gold differences scores 100% when the prediction is empty and
0% when it contains any prediction. Dataset F1 pools counts across images;
correct empty images do not add true positives. An entirely empty gold and
prediction set scores 100%.

Prediction files still use schema `1.0`. Reports now use schema `2.0` and
`scoring_method: "strict_f1"`; `correct_differences`, `matched`, `missed`, and
`extra` refer to strict matches. Partial matches appear in `detected_differences`
and `detection_matched`. The legacy weighted scores in `LEADERBOARD.md` are
archived separately and are not comparable to strict F1.

See [DESIGN.md](DESIGN.md) for the previous approach, the reasons for the change,
before-and-after examples, and the report migration details.

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

For Google's native Gemini API, use `gemini_native` with an endpoint template
and a token header. The model receives only the composite image and prompt;
annotations are used later by the local scorer.

```bash
export SPOTDIFF_API_TOKEN="your-token"

spotdiff run \
  --endpoint https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent \
  --model gemini-3.1-flash-lite \
  --protocol gemini_native \
  --token-header x-goog-api-key \
  --token-prefix "" \
  --timeout 600 \
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
