"""SpotDiff Eval: deterministic scoring for visual difference detection."""

__version__ = "0.3.0"

from .scorer import evaluate_manifest

__all__ = ["__version__", "evaluate_manifest"]
