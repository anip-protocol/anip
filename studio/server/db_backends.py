"""Database backend helpers for ANIP Studio."""

from __future__ import annotations

import os
from pathlib import Path


SUPPORTED_BACKENDS = {"postgres", "sqlite"}


def database_backend() -> str:
    value = os.getenv("STUDIO_DB_BACKEND", "postgres").strip().lower()
    if value not in SUPPORTED_BACKENDS:
        raise RuntimeError(
            f"Unsupported STUDIO_DB_BACKEND={value!r}; expected one of {sorted(SUPPORTED_BACKENDS)}"
        )
    return value


def default_database_url() -> str:
    backend = database_backend()
    if backend == "sqlite":
        sqlite_path = os.getenv("STUDIO_SQLITE_PATH", "").strip()
        if not sqlite_path:
            sqlite_path = str(Path.home() / ".anip" / "studio" / "studio.sqlite")
        return f"sqlite:///{sqlite_path}"
    return os.environ.get(
        "DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio"
    )


def migrations_dir(base_dir: Path) -> Path:
    backend = database_backend()
    candidate = base_dir / "migrations" / backend
    if candidate.exists():
        return candidate
    return base_dir / "migrations"
