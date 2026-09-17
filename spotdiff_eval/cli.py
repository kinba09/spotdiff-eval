"""Command-line interface for SpotDiff Eval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from .huggingface import DownloadError, download_dataset, token_from_environment
from .runner import DEFAULT_PROMPT, RunError, run_manifest, write_predictions
from .scorer import evaluate_manifest, write_report
from .schema import SchemaError


def _score_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _print_report(report: Dict[str, Any]) -> None:
    metrics = report["metrics"]
    counts = report["counts"]
    print(f"Overall score: {_score_percent(metrics['overall_score'])}")
    print(f"Recall: {_score_percent(metrics['recall'])}")
    print(f"Precision: {_score_percent(metrics['precision'])}")
    print(f"Attribute accuracy: {_score_percent(metrics['attribute_accuracy'])}")
    print(f"Difference coverage: {_score_percent(metrics['difference_coverage'])}")
    print(
        "Differences: "
        f"{counts['correct_differences']} correct / "
        f"{counts['gold_differences']} gold / "
        f"{counts['predicted_differences']} predicted"
    )
    print("\nPer image:")
    for item in report["items"]:
        metrics = item["metrics"]
        counts = item["counts"]
        print(
            f"  {item['item_id']}: {_score_percent(metrics['overall_score'])} "
            f"({counts['correct_differences']}/{counts['gold_differences']} correct, "
            f"{counts['extra_predictions']} extra)"
        )
    if report["unknown_prediction_items"]:
        print("\nUnknown prediction items:")
        for item in report["unknown_prediction_items"]:
            print(f"  {item['item_id']}: {item['predicted_differences']} predictions")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spotdiff", description="Evaluate structured visual spot-the-difference predictions.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate = subparsers.add_parser("evaluate", help="score a predictions JSON file against a SpotDiff manifest")
    evaluate.add_argument("--predictions", required=True, type=Path, help="model predictions JSON file")
    evaluate.add_argument("--manifest", type=Path, default=Path("data/manifest.json"), help="SpotDiff manifest JSON file")
    evaluate.add_argument("--output", type=Path, help="optional path for the full JSON report")

    download = subparsers.add_parser("download", help="download a public SpotDiff dataset from Hugging Face")
    download.add_argument("--dataset", required=True, help="Hugging Face dataset id, for example Abnik/spotdiff-v1-dev")
    download.add_argument("--output", type=Path, default=Path("."), help="directory where repository files are written")
    download.add_argument("--revision", default="main", help="Hugging Face branch, tag, or commit")
    download.add_argument("--token-env", default="HF_TOKEN", help="optional environment variable for a private dataset token")

    run = subparsers.add_parser("run", help="send composite images to a model endpoint and write predictions JSON")
    run.add_argument("--endpoint", required=True, help="model endpoint URL")
    run.add_argument("--manifest", type=Path, default=Path("data/manifest.json"), help="SpotDiff manifest JSON file")
    run.add_argument("--output", required=True, type=Path, help="output predictions JSON file")
    run.add_argument("--model", help="model name sent in the request")
    run.add_argument(
        "--protocol",
        choices=["openai_compatible", "generic_json", "gemini_native"],
        default="openai_compatible",
        help="request format expected by the endpoint",
    )
    run.add_argument("--token-env", default="SPOTDIFF_API_TOKEN", help="environment variable containing the API token")
    run.add_argument("--token-header", default="Authorization", help="HTTP header used for the token")
    run.add_argument("--token-prefix", default="Bearer", help="prefix before the token, or an empty string")
    run.add_argument("--prompt-file", type=Path, help="optional file containing the model prompt")
    run.add_argument("--timeout", type=int, default=120, help="request timeout in seconds")
    run.add_argument("--limit", type=int, help="run only the first N manifest items")
    return parser


def main(argv: Any = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "evaluate":
        try:
            report = evaluate_manifest(args.manifest, args.predictions)
            _print_report(report)
            if args.output:
                write_report(report, args.output)
                print(f"\nReport written to {args.output}")
            return 0
        except (OSError, SchemaError, ValueError, json.JSONDecodeError) as exc:
            print(f"spotdiff: error: {exc}", file=sys.stderr)
            return 2
    if args.command == "download":
        try:
            result = download_dataset(
                dataset_id=args.dataset,
                output_dir=args.output,
                revision=args.revision,
                token=token_from_environment(args.token_env),
            )
            print(f"Downloaded {len(result.files)} files from {result.dataset}@{result.revision}")
            print(f"Files written under {result.output_dir}")
            return 0
        except (DownloadError, OSError, ValueError) as exc:
            print(f"spotdiff: error: {exc}", file=sys.stderr)
            return 2
    if args.command == "run":
        try:
            prompt = DEFAULT_PROMPT
            if args.prompt_file:
                prompt = args.prompt_file.read_text(encoding="utf-8")

            import os

            token = os.environ.get(args.token_env) if args.token_env else None
            predictions = run_manifest(
                manifest_path=args.manifest,
                endpoint=args.endpoint,
                model=args.model,
                token=token,
                protocol=args.protocol,
                prompt=prompt,
                token_header=args.token_header,
                token_prefix=args.token_prefix,
                timeout=args.timeout,
                limit=args.limit,
            )
            write_predictions(predictions, args.output)
            print(f"Predictions written to {args.output}")
            print(f"Items processed: {len(predictions['items'])}")
            return 0
        except (OSError, RunError, SchemaError, ValueError, json.JSONDecodeError) as exc:
            print(f"spotdiff: error: {exc}", file=sys.stderr)
            return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
