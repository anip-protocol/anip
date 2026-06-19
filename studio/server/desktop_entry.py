"""Desktop-packaged Studio API entry point."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def _runtime_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root).resolve()
    return Path(__file__).resolve().parents[2]


def main() -> None:
    os.environ.setdefault("ANIP_STUDIO_RUNTIME_ROOT", str(_runtime_root()))
    os.environ.setdefault("STUDIO_MODE", "desktop")
    os.environ.setdefault("STUDIO_DB_BACKEND", "sqlite")
    os.environ.setdefault("ANIP_STUDIO_DESKTOP_DATA_DIR", str(Path.home() / ".anip" / "studio"))
    os.environ.setdefault(
        "STUDIO_SQLITE_PATH",
        str(Path(os.environ["ANIP_STUDIO_DESKTOP_DATA_DIR"]) / "studio.sqlite"),
    )
    os.environ.setdefault("STUDIO_SEED_SHOWCASES", "1")
    os.environ.setdefault("STUDIO_SEED_PROFILE", "public_showcase")
    os.environ.setdefault("STUDIO_READ_ONLY", "0")
    os.environ.setdefault("STUDIO_RUN_MIGRATIONS", "1")

    Path(os.environ["STUDIO_SQLITE_PATH"]).parent.mkdir(parents=True, exist_ok=True)

    from studio.server.app import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.getenv("STUDIO_DESKTOP_API_PORT", "8100")),
        log_level=os.getenv("STUDIO_DESKTOP_API_LOG_LEVEL", "warning"),
    )


if __name__ == "__main__":
    main()
