"""SpotDiff Eval: deterministic scoring for visual difference detection."""

__version__ = "0.1.0"

from .scorer import evaluate_manifest

__all__ = ["__version__", "evaluate_manifest"]
