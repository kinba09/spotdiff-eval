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
| qwen3-vl-32b-instruct ([predictions](predictions/qwen3-vl-32b-instruct.json)) | 30.1% | 3.3% | 24.6% | 45.5% | 26.7% | 0.2.2 |
| gemma4-31b-it ([predictions](predictions/gemma4-31b-it.json)) | 25.5% | 4.9% | 13.1% | 38.1% | 54.2% | 0.2.2 |
| llama4-scout-17b ([predictions](predictions/llama4-scout-17b.json)) | 14.0% | 0.0% | 3.3% | 18.2% | 50.0% | 0.2.2 |

These runs used the ASU OpenAI-compatible endpoint with the standard
`spotdiff_eval/prompts/spotdiff_v1.txt` prompt and the command pattern shown
above. The models received only the composite images from `data/images/`;
annotation files were used locally by the scorer after prediction generation.

The following requested models did not produce valid scored predictions:

- `qwen3-vl-32b-thinking`: timed out after 180 seconds per request.
- `llama4-maverick-17b`: endpoint returned HTTP 400.
- `glm-4-5v`: returned invalid prediction JSON (`from` was empty).
- `gemma3-27b-it`: endpoint returned HTTP 503.

## Future official split

A future hidden test split can support an independently verified leaderboard.
