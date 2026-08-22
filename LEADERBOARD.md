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

## Future official split

A future hidden test split can support an independently verified leaderboard.
