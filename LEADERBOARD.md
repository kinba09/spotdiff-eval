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

**Overall score is the final benchmark result.** It balances finding the
differences and avoiding incorrect answers. All percentages run from 0% to
100%; higher is better. The metric names appear in brackets for reference.

These results use evaluator `0.3.0` and re-score saved predictions. Only
complete, correct descriptions count toward the overall score. Conservative
text matching can reject valid paraphrases. Historical scores appear in the
archive below and use a different formula.

| Model | **Overall score [F1]** | Differences found [Recall] | Correct answers [Precision] | Correct / expected | Evaluator |
| --- | ---: | ---: | ---: | ---: | --- |
| Perfect fixture (annotation oracle) | **100.0%** | 100.0% | 100.0% | 61 / 61 | 0.3.0 |
| GPT-6 Astra, Codex subagent ([predictions](predictions/gpt-6-astra.json)) | **27.3%** | 24.6% | 30.6% | 15 / 61 | 0.3.0 |
| GPT-6.1 Terra, Codex subagent ([predictions](predictions/gpt-6.1-terra.json)) | **25.5%** | 19.7% | 36.4% | 12 / 61 | 0.3.0 |
| GPT-6.1 Sol, Codex subagent ([predictions](predictions/gpt-6.1-sol.json)) | **19.8%** | 16.4% | 25.0% | 10 / 61 | 0.3.0 |
| GPT-6 Luna, Codex subagent ([predictions](predictions/gpt-6-luna.json)) | **16.7%** | 9.8% | 54.5% | 6 / 61 | 0.3.0 |
| gemini-3.1-flash-lite ([predictions](predictions/gemini-3.1-flash-lite.json)) | **7.3%** | 4.9% | 14.3% | 3 / 61 | 0.3.0 |
| gemma4-31b-it ([predictions](predictions/gemma4-31b-it.json)) | **4.9%** | 3.3% | 9.5% | 2 / 61 | 0.3.0 |
| qwen3-vl-32b-instruct ([predictions](predictions/qwen3-vl-32b-instruct.json)) | **2.1%** | 1.6% | 3.0% | 1 / 61 | 0.3.0 |
| llama4-scout-17b ([predictions](predictions/llama4-scout-17b.json)) | **0.0%** | 0.0% | 0.0% | 0 / 61 | 0.3.0 |

- **Differences found [Recall]:** how many expected differences the model
  described completely and correctly.
- **Correct answers [Precision]:** how many reported differences were
  completely correct.

### GPT-6.1 Sol, GPT-6.1 Terra, and GPT-6 Astra run details

Each model ran as an independent Codex subagent, visually inspected all ten
composite images, and used the built-in `spotdiff_eval/prompts/spotdiff_v1.txt`
prompt. The subagents did not access annotations or other model predictions.

| Model identifier | Evaluator | Evaluation command |
| --- | --- | --- |
| `gpt-6.1-sol` | 0.3.0 | `python3 -m spotdiff_eval.cli evaluate --manifest data/manifest.json --predictions predictions/gpt-6.1-sol.json --output results/gpt-6.1-sol.json` |
| `gpt-6.1-terra` | 0.3.0 | `python3 -m spotdiff_eval.cli evaluate --manifest data/manifest.json --predictions predictions/gpt-6.1-terra.json --output results/gpt-6.1-terra.json` |
| `gpt-6-astra` | 0.3.0 | `python3 -m spotdiff_eval.cli evaluate --manifest data/manifest.json --predictions predictions/gpt-6-astra.json --output results/gpt-6-astra.json` |

Hardware is not applicable; these are hosted Codex models.

## Archived weighted results (before 0.3.0)

These historical results used `0.60 * recall + 0.25 * precision + 0.15 *
attribute_accuracy`, with partial detections contributing to recall and precision.

| Model | Historical overall [Weighted score] | Differences fully found [Coverage] | Changes noticed [Recall] | Relevant answers [Precision] | Detail accuracy [Attribute accuracy] | Evaluator |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Perfect baseline | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.2.0 |
| gemini-3.1-flash-lite ([predictions](predictions/gemini-3.1-flash-lite.json)) | 32.8% | 4.9% | 19.7% | 57.1% | 44.4% | 0.2.2 |
| qwen3-vl-32b-instruct ([predictions](predictions/qwen3-vl-32b-instruct.json)) | 30.1% | 3.3% | 24.6% | 45.5% | 26.7% | 0.2.2 |
| gemma4-31b-it ([predictions](predictions/gemma4-31b-it.json)) | 25.5% | 4.9% | 13.1% | 38.1% | 54.2% | 0.2.2 |
| llama4-scout-17b ([predictions](predictions/llama4-scout-17b.json)) | 14.0% | 0.0% | 3.3% | 18.2% | 50.0% | 0.2.2 |
| GPT-6 Luna, Codex subagent ([predictions](predictions/gpt-6-luna.json)) | 37.3% | 9.8% | 13.1% | 72.7% | 75.0% | 0.2.0* |

### Archived GPT-6 Luna run details

- Model identifier: `gpt-6-luna`
- Provider/runtime: Codex subagent
- Prompt: built-in `spotdiff_eval/prompts/spotdiff_v1.txt`
- Evaluator version: `0.2.0` as recorded in the generated score report
- Command: `python3 -m spotdiff_eval.cli evaluate --manifest data/manifest.json --predictions predictions/gpt-6-luna.json --output results/gpt-6-luna.json`
- Hardware: not applicable (hosted model)

\* The legacy scorer report labeled itself `0.2.0` while that checkout's package
metadata said `0.2.2`. Evaluator `0.3.0` reports the package version consistently.

## Future official split

A future hidden test split can support an independently verified leaderboard.
