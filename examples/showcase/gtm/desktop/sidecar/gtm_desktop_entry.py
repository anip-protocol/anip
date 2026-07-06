"""Desktop-packaged GTM Agent runtime entry point.

The desktop app launches this one sidecar process. The sidecar starts the
generated Python ANIP services on loopback ports, configures the existing GTM
LLM agent runtime to discover those services, and serves the GTM Agent web UI.
"""

from __future__ import annotations

import importlib
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


SERVICE_MODULES = [
    ("pipeline", "gtm-pipeline-service", "gtm_pipeline_q2_review.app"),
    ("enrichment", "gtm-enrichment-service", "gtm_pipeline_q2_review.services.gtm_enrichment_service.app"),
    ("prioritization", "gtm-prioritization-service", "gtm_pipeline_q2_review.services.gtm_prioritization_service.app"),
    ("outreach", "gtm-outreach-service", "gtm_pipeline_q2_review.services.gtm_outreach_service.app"),
]


def _runtime_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root).resolve()
    return Path(__file__).resolve().parents[5]


def _append_sys_path(path: Path) -> None:
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)


def _configure_import_paths(root: Path) -> None:
    generated_dir = _generated_dir(root)
    for path in [
        root,
        root / "examples" / "showcase" / "gtm" / "agents" / "llm_runtime",
        generated_dir / "src",
        root / "packages" / "python" / "anip-core" / "src",
        root / "packages" / "python" / "anip-crypto" / "src",
        root / "packages" / "python" / "anip-server" / "src",
        root / "packages" / "python" / "anip-service" / "src",
        root / "packages" / "python" / "anip-fastapi" / "src",
        root / "packages" / "python" / "anip-runtime-utils" / "src",
    ]:
        _append_sys_path(path)


def _generated_dir(root: Path) -> Path:
    override = os.getenv("GTM_DESKTOP_GENERATED_DIR")
    if override:
        return Path(override).resolve()
    return root / "examples" / "showcase" / "gtm" / "generated" / "language-parity" / "python"


def _data_dir() -> Path:
    override = os.getenv("ANIP_GTM_DESKTOP_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    else:
        path = Path.home() / ".anip" / "gtm-agent-desktop"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _settings_json() -> dict[str, Any]:
    path = _data_dir() / "settings.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _bundled_sqlite_path(root: Path) -> Path:
    return root / "examples" / "showcase" / "gtm" / "desktop" / "data" / "gtm_desktop.sqlite"


def _configure_local_data_backend(root: Path) -> str:
    if os.getenv("DATABASE_URL") or os.getenv("GTM_DESKTOP_DATABASE_URL"):
        url = os.getenv("GTM_DESKTOP_DATABASE_URL") or os.getenv("DATABASE_URL") or ""
        os.environ["DATABASE_URL"] = url
        return "external-postgres" if url.startswith("postgres") else "sqlite" if url.startswith("sqlite") else "custom"
    sqlite_path = _bundled_sqlite_path(root)
    if not sqlite_path.exists():
        os.environ.setdefault("DATABASE_URL", "")
        return "not_configured"
    os.environ["DATABASE_URL"] = f"sqlite:///{sqlite_path}"
    return "sqlite"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _configured_runtime_port() -> int:
    raw = os.getenv("GTM_DESKTOP_API_PORT") or os.getenv("PORT")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return 9310


def _runtime_module(generated_dir: Path) -> str:
    candidates = [
        path.parent.parent.name
        for path in (generated_dir / "src").glob("*/runtime/actor.py")
        if path.parent.parent.name and not path.parent.parent.name.startswith(".")
    ]
    if len(candidates) == 1:
        return candidates[0]

    # PyInstaller can import the generated package even when source files are
    # not visible as normal filesystem paths. Keep the fallback explicit to the
    # packaged GTM showcase instead of guessing from broad module scans.
    fallback = "gtm_pipeline_q2_review"
    try:
        importlib.import_module(f"{fallback}.runtime.actor")
        return fallback
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Expected exactly one generated Python runtime package under "
            f"{generated_dir / 'src'}, found {candidates or 'none'}."
        ) from exc


def _api_keys_json(generated_dir: Path) -> str:
    runtime_module = _runtime_module(generated_dir)
    actor_module = importlib.import_module(f"{runtime_module}.runtime.actor")
    return json.dumps(
        {
            profile.api_key: actor_module.encode_actor_principal(profile)
            for profile in actor_module.actor_profiles().values()
        }
    )


def _actors_json(generated_dir: Path) -> str:
    runtime_module = _runtime_module(generated_dir)
    actor_module = importlib.import_module(f"{runtime_module}.runtime.actor")
    actors: list[dict[str, Any]] = []
    for profile in actor_module.actor_profiles().values():
        item = {key: value for key, value in profile.__dict__.items() if key != "api_key"}
        item["bearer_token"] = profile.api_key
        item["label"] = item.get("label") or f"{item.get('display_name', item.get('actor_id'))} · {item.get('role')}"
        actors.append(item)
    return json.dumps(actors)


def _ensure_key_file(data_dir: Path) -> None:
    from anip_crypto import KeyManager

    data_dir.mkdir(parents=True, exist_ok=True)
    key_path = data_dir / "anip-keys"
    if key_path.exists():
        try:
            json.loads(key_path.read_text())
            return
        except json.JSONDecodeError:
            key_path.unlink()
    KeyManager(str(key_path))


def _service_config(service_ports: dict[str, int]) -> list[dict[str, str]]:
    services: list[dict[str, str]] = []
    for name, _service_id, _module_name in SERVICE_MODULES:
        service = {"name": name, "url": f"http://127.0.0.1:{service_ports[name]}"}
        if name in {"pipeline", "prioritization"}:
            service["approval_list_path"] = "/gtm/approvals"
            service["approval_approve_path_template"] = "/gtm/approvals/{approval_request_id}/approve"
        services.append(service)
    return services


def _wait_for_port(port: int, *, timeout_seconds: float = 12.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for 127.0.0.1:{port}")


def _start_uvicorn_thread(app: FastAPI, *, port: int, name: str, log_level: str) -> threading.Thread:
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level=log_level, access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name=name, daemon=True)
    thread.start()
    _wait_for_port(port)
    return thread


def _start_services(service_ports: dict[str, int], *, log_level: str) -> list[threading.Thread]:
    threads: list[threading.Thread] = []
    for name, _service_id, module_name in SERVICE_MODULES:
        module = importlib.import_module(module_name)
        app = module.create_app()
        threads.append(_start_uvicorn_thread(app, port=service_ports[name], name=f"gtm-{name}", log_level=log_level))
    return threads


def _configure_agent_environment(root: Path, generated_dir: Path, service_ports: dict[str, int]) -> None:
    os.environ.setdefault("ANIP_AGENT_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.4-mini"))
    os.environ.setdefault("ANIP_AGENT_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    os.environ.setdefault("ANIP_AGENT_TEMPERATURE", "0.1")
    os.environ.setdefault("ANIP_AGENT_TIMEOUT_SECONDS", "45")
    os.environ.setdefault("ANIP_AGENT_MODEL_MAX_RETRIES", "8")
    os.environ.setdefault("ANIP_AGENT_CATALOG_TTL_SECONDS", "5")
    os.environ.setdefault("ANIP_AGENT_APP_MODULE", "gtm_agent_app")
    os.environ.setdefault("ANIP_AGENT_CONSUMPTION_KIT_DIR", str(generated_dir / "agent-consumption"))
    os.environ.setdefault("ANIP_AGENT_DEFAULT_ACTOR_ID", "sales_leader")
    os.environ.setdefault("ANIP_AGENT_LANGUAGE", "desktop-python")
    os.environ.setdefault("ANIP_AGENT_README_URL", "https://github.com/anip-protocol/anip/tree/main/examples/showcase/gtm")
    os.environ.setdefault("ANIP_AGENT_DOCS_BASE_URL", "https://anip.dev")
    os.environ.setdefault("ANIP_AGENT_SERVICES_JSON", json.dumps(_service_config(service_ports)))
    os.environ.setdefault("ANIP_AGENT_ACTORS_JSON", _actors_json(generated_dir))
    if os.getenv("OPENAI_API_KEY") and not os.getenv("ANIP_AGENT_API_KEY"):
        os.environ["ANIP_AGENT_API_KEY"] = os.environ["OPENAI_API_KEY"]

    _configure_local_data_backend(root)
    os.environ.setdefault("ANIP_AGENT_SETTINGS_PATH", str(_data_dir() / "settings.json"))
    os.environ.setdefault("GTM_APPROVAL_STORE_PATH", str(_data_dir() / "approvals.json"))
    os.environ.setdefault("GTM_GENERATED_DIR", str(generated_dir))
    os.environ.setdefault("GTM_DESKTOP_RUNTIME_ROOT", str(root))


def _build_agent_app(root: Path, generated_dir: Path, service_ports: dict[str, int]) -> FastAPI:
    _configure_agent_environment(root, generated_dir, service_ports)
    module = importlib.import_module("app")
    app: FastAPI = module.app
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^(tauri://localhost|https?://tauri\.localhost|https?://localhost(:\d+)?|https?://127\.0\.0\.1(:\d+)?)$",
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/desktop/health")
    def desktop_health() -> dict[str, Any]:
        data_backend_kind = _configure_local_data_backend(root)
        return {
            "status": "ok",
            "runtime": "gtm-agent-desktop",
            "agent_url": f"http://127.0.0.1:{_configured_runtime_port()}",
            "services": _service_config(service_ports),
            "data_backend": {
                "kind": data_backend_kind,
                "configured": data_backend_kind != "not_configured",
            },
            "llm": {
                "model": str(_settings_json().get("model") or os.getenv("ANIP_AGENT_MODEL") or ""),
                "base_url": str(_settings_json().get("base_url") or os.getenv("ANIP_AGENT_BASE_URL") or os.getenv("OPENAI_BASE_URL") or ""),
                "api_key_configured": bool(os.getenv("ANIP_AGENT_API_KEY") or _settings_json().get("api_key")),
            },
        }

    return app


def main() -> None:
    root = _runtime_root()
    _configure_import_paths(root)
    data_dir = _data_dir()
    os.chdir(data_dir)
    generated_dir = _generated_dir(root)
    _ensure_key_file(data_dir)

    os.environ["ANIP_API_KEYS_JSON"] = _api_keys_json(generated_dir)

    service_ports = {name: _free_port() for name, _service_id, _module_name in SERVICE_MODULES}
    log_level = os.getenv("GTM_DESKTOP_LOG_LEVEL", "warning")
    _start_services(service_ports, log_level=log_level)

    runtime_port = _configured_runtime_port()
    app = _build_agent_app(root, generated_dir, service_ports)
    uvicorn.run(app, host="127.0.0.1", port=runtime_port, log_level=log_level)


if __name__ == "__main__":
    main()
