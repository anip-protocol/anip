"""Runtime resource paths for source-tree and desktop-packaged Studio."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def repo_root() -> Path:
    configured = os.getenv("ANIP_STUDIO_RUNTIME_ROOT", "").strip()
    if configured:
        return Path(configured).resolve()

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root).resolve()

    return Path(__file__).resolve().parents[2]


def runtime_path(*parts: str) -> Path:
    return repo_root().joinpath(*parts)


def server_path(*parts: str) -> Path:
    return runtime_path("studio", "server", *parts)


def tooling_schema_path(*parts: str) -> Path:
    return runtime_path("tooling", "schemas", *parts)
