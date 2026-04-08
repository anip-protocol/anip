"""Helpers for Studio project consumer-mode labels."""

from __future__ import annotations

from typing import Iterable


DEFAULT_CONSUMER_MODE = "hybrid"
CONSUMER_LABEL_PREFIX = "consumer:"

CONSUMER_MODE_LABELS = {
    "human_app": "People through an app",
    "agent_anip": "Agents and tools through ANIP",
    "hybrid": "Both people and agents",
}


def normalize_consumer_mode(value: str | None) -> str:
    cleaned = (value or "").strip().lower()
    if cleaned in CONSUMER_MODE_LABELS:
        return cleaned
    return DEFAULT_CONSUMER_MODE


def consumer_mode_from_labels(labels: Iterable[str] | None) -> str:
    for label in labels or []:
        if isinstance(label, str) and label.startswith(CONSUMER_LABEL_PREFIX):
            return normalize_consumer_mode(label[len(CONSUMER_LABEL_PREFIX) :])
    return DEFAULT_CONSUMER_MODE


def consumer_mode_label(mode: str | None) -> str:
    normalized = normalize_consumer_mode(mode)
    return CONSUMER_MODE_LABELS[normalized]


def consumer_mode_tag(mode: str | None) -> str:
    return f"{CONSUMER_LABEL_PREFIX}{normalize_consumer_mode(mode)}"
