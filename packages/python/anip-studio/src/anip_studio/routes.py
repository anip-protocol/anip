"""ANIP Studio — mount the inspection UI at /studio on a FastAPI app."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from anip_service import ANIPService


def mount_anip_studio(
    app: FastAPI,
    service: ANIPService,
    prefix: str = "/studio",
) -> None:
    """Mount the ANIP Studio inspection UI.

    Serves the pre-built Vue SPA at {prefix}/ and provides
    a bootstrap config at {prefix}/config.json.
    """
    static_dir = Path(__file__).parent / "static"

    if not static_dir.exists():
        import warnings
        warnings.warn(
            "ANIP Studio static assets not found. "
            "Run 'cd studio && npm run build && bash sync.sh' to build them.",
            stacklevel=2,
        )
        return

    index_html = static_dir / "index.html"

    # Bootstrap config (dynamically generated)
    @app.get(f"{prefix}/config.json")
    async def studio_config():
        return JSONResponse({
            "service_id": service.service_id,
            "embedded": True,
        })

    # Index route
    @app.get(f"{prefix}")
    @app.get(f"{prefix}/")
    async def studio_index():
        return FileResponse(index_html, media_type="text/html")

    # Static assets (CSS/JS bundles)
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount(
            f"{prefix}/assets",
            StaticFiles(directory=str(assets_dir)),
            name="studio-assets",
        )

    # SPA catch-all for client-side routing
    @app.get(f"{prefix}/{{path:path}}")
    async def studio_spa_fallback(path: str):
        file_path = static_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(index_html, media_type="text/html")
