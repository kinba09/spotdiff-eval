# Run SpotDiff with your coding agent

Replace `<MODEL_NAME>` with the vision model you want to test, then paste this
into your coding agent:

```text
Clone https://github.com/kinba09/spotdiff-eval if needed.
Read RUN_BENCHMARK.md and run the full SpotDiff benchmark on <MODEL_NAME>.
Launch a fresh instance of that exact model using your available model tools,
an API, or a local runtime. Save its answers, run the evaluator, and report the
Overall score [F1] with links to the predictions and results.
```

The agent handles setup, model execution, output formatting, and scoring using
the instructions below. The chosen model must support image input.

## Instructions for the coding agent

### 1. Set up the repository

Work from the repository root. Create a Python environment and install:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

The development images and manifest are included in the repository. Use
`data/manifest.json` to enumerate every image and its item ID.

### 2. Launch the chosen model

Use whichever route is available for the requested model:

| Route | How to run it |
| --- | --- |
| Your agent can launch another model | Start a fresh, isolated model session or subagent with the exact requested model selected. |
| A hosted API is configured | Call that model through its API. The built-in runner supports OpenAI-compatible endpoints and native Gemini endpoints. |
| The model runs locally | Start it with the available local runtime and send images through its vision API or SDK. |

Confirm the actual model identifier before running. If model access,
credentials, or sufficient local hardware is missing, ask for the specific
missing information. Report a blocked run if that model cannot be launched;
never silently substitute another model or label the controlling agent's own
answers as the requested model's output.

### 3. Collect answers from every image

Give the model the exact prompt from
[`spotdiff_eval/prompts/spotdiff_v1.txt`](spotdiff_eval/prompts/spotdiff_v1.txt)
and one complete composite image per request. Each image contains both panels.
Use a fresh conversation for each image where the runtime supports it.

The answering model should receive only the benchmark prompt, image, and output
format instructions. Keep gold annotation files, existing predictions,
leaderboard answers, and the controlling agent's analysis out of its context.
For a subagent, use a fresh context and restrict its inputs to the provided
prompt and images; do not give it a task that requires searching the repository.

Collect the model's `{"differences": [...]}` response for each image. Combine
the responses into `predictions/<model-slug>-<run-id>.json`, using:

- `schema_version`: `"1.0"`.
- `model`: the exact model identifier that ran.
- `items`: one entry per manifest item, each containing its `item_id` and the
  model-produced `differences` array.

Follow [`schemas/prediction.schema.json`](schemas/prediction.schema.json).
Preserve the model's answers; formatting them into the required document must
not rewrite subjects or details to improve their score. Use a unique run ID so
previous runs are preserved. Report failures explicitly; an API error or invalid
response is not an empty answer.

For an OpenAI-compatible endpoint, the built-in runner performs these calls
and writes the prediction document:

```bash
.venv/bin/python -m spotdiff_eval.cli run \
  --endpoint "<CHAT_COMPLETIONS_URL>" \
  --model "<MODEL_NAME>" \
  --manifest data/manifest.json \
  --output "predictions/<model-slug>-<run-id>.json"
```

Use an existing `SPOTDIFF_API_TOKEN` environment variable for authentication
when required. Keep tokens out of prediction files and reports. For native
Gemini, see the [endpoint example in README.md](README.md#optional-endpoint-runner).

### 4. Score the saved answers

Check that every manifest item has a model response before calling a run
complete. Then run:

```bash
.venv/bin/python -m spotdiff_eval.cli evaluate \
  --manifest data/manifest.json \
  --predictions "predictions/<model-slug>-<run-id>.json" \
  --output "results/<model-slug>-<run-id>.json"
```

Use the saved prediction file as-is. Partial runs must be labeled partial:
the evaluator treats missing items as empty answers. Use the deterministic
Overall score produced by the current evaluator.

### 5. Return the result

Lead with **Overall score: X% [F1]**, followed by:

- The actual model identifier, execution route, and whether the run is complete.
- **Differences found [Recall]** and **Correct answers [Precision]**.
- Links or paths to the predictions and result JSON files.
- The dataset version, evaluator version, repository commit, exact run commands,
  and generation settings. For local execution, include runtime and hardware.
- Any failures, retries, or deviations from the built-in prompt.

This is a public development benchmark. Keep leaderboard changes separate
unless the user also asks to submit the result.
