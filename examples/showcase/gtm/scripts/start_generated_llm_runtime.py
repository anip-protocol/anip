"""Start the generated GTM ANIP LLM runtime with the local generated services.

This is a development helper for benchmark and smoke-test runs. It keeps the
runtime wiring out of fragile shell one-liners while still using generic ANIP
agent runtime code plus the generated agent-consumption kit.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

import uvicorn


REPO_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_DIR = REPO_ROOT / "examples" / "showcase" / "gtm" / "agents" / "llm_runtime"
RUNTIME_UTILS_DIR = REPO_ROOT / "packages" / "python" / "anip-runtime-utils" / "src"
DEFAULT_GENERATED_DIR = REPO_ROOT / "examples" / "showcase" / "gtm" / "generated" / "go_registry_gtm_pipeline_custom"


def _load_api_key() -> tuple[str, str]:
    direct_key = (os.getenv("STUDIO_SIMULATOR_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    if direct_key:
        return direct_key, os.getenv("STUDIO_SIMULATOR_BASE_URL") or "https://api.openai.com/v1"

    sys.path.insert(0, str(REPO_ROOT))
    studio_database_url = (os.getenv("STUDIO_DATABASE_URL") or "").strip()
    original_database_url = os.environ.get("DATABASE_URL")
    if studio_database_url:
        os.environ["DATABASE_URL"] = studio_database_url
    from studio.server.simulator_provider import load_simulator_provider_resolution

    try:
        config = load_simulator_provider_resolution().config
    finally:
        if studio_database_url:
            if original_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = original_database_url
    if not config.api_key:
        raise RuntimeError("Stored simulator API key is not configured")
    return config.api_key, config.base_url or "https://api.openai.com/v1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9304)
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    api_key, base_url = _load_api_key()
    generated_dir = Path(os.getenv("GTM_GENERATED_DIR", str(DEFAULT_GENERATED_DIR))).resolve()

    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(RUNTIME_UTILS_DIR))
    sys.path.insert(0, str(RUNTIME_DIR))
    sys.path.insert(0, str(generated_dir / "src"))

    default_services = [
        {
            "name": "pipeline",
            "url": "http://127.0.0.1:4100",
            "approval_list_path": "/gtm/approvals",
            "approval_approve_path_template": "/gtm/approvals/{approval_request_id}/approve",
        },
        {"name": "enrichment", "url": "http://127.0.0.1:4101"},
        {
            "name": "prioritization",
            "url": "http://127.0.0.1:4102",
            "approval_list_path": "/gtm/approvals",
            "approval_approve_path_template": "/gtm/approvals/{approval_request_id}/approve",
        },
        {"name": "outreach", "url": "http://127.0.0.1:4103"},
    ]
    services = json.loads(os.getenv("GTM_AGENT_SERVICES_JSON", "null") or "null") or default_services
    try:
        from shared.actor_identity import actor_profiles
    except ModuleNotFoundError:
        package_dirs = [
            path
            for path in (generated_dir / "src").iterdir()
            if path.is_dir() and (path / "runtime" / "actor.py").exists()
        ]
        if not package_dirs:
            raise
        actor_module = importlib.import_module(f"{package_dirs[0].name}.runtime.actor")
        actor_profiles = actor_module.actor_profiles

    actors = []
    for profile in actor_profiles().values():
        public_profile = {
            key: value
            for key, value in profile.__dict__.items()
            if key != "api_key"
        }
        public_profile["bearer_token"] = profile.api_key
        actors.append(public_profile)

    os.environ.update(
        {
            "ANIP_AGENT_API_KEY": api_key,
            "ANIP_AGENT_MODEL": args.model,
            "ANIP_AGENT_BASE_URL": base_url,
            "ANIP_AGENT_TEMPERATURE": "0.1",
            "ANIP_AGENT_TIMEOUT_SECONDS": "45",
            "ANIP_AGENT_MODEL_MAX_RETRIES": "8",
            "ANIP_AGENT_CATALOG_TTL_SECONDS": "5",
            "ANIP_AGENT_APP_MODULE": "gtm_agent_app",
            "ANIP_AGENT_CONSUMPTION_KIT_DIR": str(generated_dir / "agent-consumption"),
            "ANIP_AGENT_DEFAULT_ACTOR_ID": "sales_leader",
            "ANIP_AGENT_SERVICES_JSON": json.dumps(services),
            "ANIP_AGENT_ACTORS_JSON": json.dumps(actors),
        }
    )

    uvicorn.run("app:app", host=args.host, port=args.port, log_level=args.log_level)


if __name__ == "__main__":
    main()
