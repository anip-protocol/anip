"""Public ANIP evaluator package surface.

The CLI entrypoint remains ``tooling/bin/anip_design_validate.py`` for
compatibility, but the evaluator logic lives in this package so it can be
reviewed, tested, and evolved as a subsystem rather than as one large script.
"""

from .categories import (
    CATEGORY_EVALUATORS,
    evaluate,
    evaluate_cross_service,
    evaluate_generic,
    evaluate_observability,
    evaluate_orchestration,
    evaluate_recovery,
    evaluate_safety,
)
from .io import SCHEMA_DIR, load_json, load_yaml, validate_payload
from .report import to_markdown

__all__ = [
    "CATEGORY_EVALUATORS",
    "SCHEMA_DIR",
    "evaluate",
    "evaluate_cross_service",
    "evaluate_generic",
    "evaluate_observability",
    "evaluate_orchestration",
    "evaluate_recovery",
    "evaluate_safety",
    "load_json",
    "load_yaml",
    "to_markdown",
    "validate_payload",
]
