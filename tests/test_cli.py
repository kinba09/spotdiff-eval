import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from spotdiff_eval import __version__
from spotdiff_eval.cli import main


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_evaluate_displays_plain_language_scores_and_writes_versioned_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main([
                    "evaluate", "--manifest", str(ROOT / "data/manifest.json"),
                    "--predictions", str(ROOT / "predictions/example.json"),
                    "--output", str(output),
                ])
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue().splitlines()[0], "Overall score: 6.3% [F1]")
        self.assertIn("This is the final benchmark result.", stdout.getvalue())
        self.assertIn("Differences found: 3.3% [Recall]", stdout.getvalue())
        self.assertIn("Correct answers: 100.0% [Precision]", stdout.getvalue())
        self.assertIn("Additional details (including partial matches):", stdout.getvalue())
        self.assertIn("Detail accuracy: 100.0% [Attribute accuracy]", stdout.getvalue())
        self.assertNotIn("Strict recall", stdout.getvalue())
        self.assertNotIn("Strict precision", stdout.getvalue())
        self.assertNotIn("Difference coverage:", stdout.getvalue())
        self.assertEqual(report["schema_version"], "2.0")
        self.assertEqual(report["evaluator_version"], __version__)
        self.assertEqual(report["scoring_method"], "strict_f1")
        self.assertEqual(report["metrics"]["overall_score"], report["metrics"]["f1"])


if __name__ == "__main__":
    unittest.main()
