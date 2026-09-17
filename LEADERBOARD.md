# SpotDiff Community Leaderboard

This is a community-reported leaderboard for the public `spotdiff-v1-dev`
release. Since the annotations are public, entries are intended for
reproducibility and development comparison rather than a security-sensitive
official ranking.

## Submission format

Open a pull request adding a row to the table and include:

- model name and exact version
- provider or local runtime
- evaluator version
- predictions file or a reproducible link
- command used to evaluate
- hardware, if relevant

Run:

```bash
python3 -m spotdiff_eval.cli evaluate \
  --manifest data/manifest.json \
  --predictions predictions/your-model.json \
  --output results/your-model.json
```

## Results

| Model | Overall | Coverage | Recall | Precision | Attribute accuracy | Evaluator |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Perfect baseline | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.2.0 |
| gemini-3.1-flash-lite ([predictions](predictions/gemini-3.1-flash-lite.json)) | 32.8% | 4.9% | 19.7% | 57.1% | 44.4% | 0.2.2 |
| qwen3-vl-32b-instruct ([predictions](predictions/qwen3-vl-32b-instruct.json)) | 30.1% | 3.3% | 24.6% | 45.5% | 26.7% | 0.2.2 |
| gemma4-31b-it ([predictions](predictions/gemma4-31b-it.json)) | 25.5% | 4.9% | 13.1% | 38.1% | 54.2% | 0.2.2 |
| llama4-scout-17b ([predictions](predictions/llama4-scout-17b.json)) | 14.0% | 0.0% | 3.3% | 18.2% | 50.0% | 0.2.2 |

## Future official split

A future hidden test split can support an independently verified leaderboard.
