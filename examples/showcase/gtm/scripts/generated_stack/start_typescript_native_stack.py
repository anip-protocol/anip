"""Start the GTM TypeScript-native language-parity stack.

The parity topology intentionally mirrors the Python reference topology:
pipeline, enrichment, prioritization, and outreach are separate ANIP service
endpoints. Do not point four logical service names at one aggregate endpoint;
that duplicates catalog discovery and makes LLM planning slow and misleading.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_GENERATED_DIR = REPO_ROOT / "output" / "gtm-language-parity" / "typescript-native"
START_RUNTIME = REPO_ROOT / "examples" / "showcase" / "gtm" / "scripts" / "start_generated_llm_runtime.py"
SERVICE_SLICES = [
    ("pipeline", "gtm-pipeline-service"),
    ("enrichment", "gtm-enrichment-service"),
    ("prioritization", "gtm-prioritization-service"),
    ("outreach", "gtm-outreach-service"),
]


def _api_keys_json() -> str:
    sys.path.insert(0, str(REPO_ROOT))
    from examples.showcase.gtm.shared.actor_identity import actor_profiles, encode_actor_principal

    return json.dumps({profile.api_key: encode_actor_principal(profile) for profile in actor_profiles().values()})


def _service_config(base_port: int) -> list[dict[str, str]]:
    services: list[dict[str, str]] = []
    for index, (name, _service_id) in enumerate(SERVICE_SLICES):
        service = {
            "name": name,
            "url": f"http://127.0.0.1:{base_port + index}",
        }
        if name in {"pipeline", "prioritization"}:
            service["approval_list_path"] = "/gtm/approvals"
            service["approval_approve_path_template"] = "/gtm/approvals/{approval_request_id}/approve"
        services.append(service)
    return services


def _start_services(args: argparse.Namespace) -> list[subprocess.Popen[bytes]]:
    generated_dir = Path(args.generated_dir).resolve()
    if not (generated_dir / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=generated_dir, check=True)
    api_keys = _api_keys_json()
    processes: list[subprocess.Popen[bytes]] = []
    for index, (_name, service_id) in enumerate(SERVICE_SLICES):
        env = os.environ.copy()
        env.update(
            {
                "PYTHONPATH": str(REPO_ROOT),
                "ANIP_API_KEYS_JSON": api_keys,
                "DATABASE_URL": args.database_url,
                "PORT": str(args.base_port + index),
                "GTM_SERVICE_FILTER": service_id,
                "ANIP_SERVICE_ID": service_id,
            }
        )
        processes.append(subprocess.Popen(["npm", "run", "dev"], cwd=generated_dir, env=env))
    return processes


def _start_runtime(args: argparse.Namespace) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": os.pathsep.join([str(REPO_ROOT / "examples" / "showcase" / "gtm"), str(REPO_ROOT)]),
            "ANIP_AGENT_APP_MODULE": "gtm_agent_app",
            "OPENAI_MODEL": args.model,
            "DATABASE_URL": args.database_url,
            "STUDIO_DATABASE_URL": args.database_url,
            "GTM_GENERATED_DIR": str(Path(args.generated_dir).resolve()),
            "GTM_AGENT_SERVICES_JSON": json.dumps(_service_config(args.base_port)),
        }
    )
    return subprocess.Popen(
        [
            sys.executable,
            str(START_RUNTIME),
            "--port",
            str(args.runtime_port),
            "--model",
            args.model,
            "--log-level",
            args.log_level,
        ],
        cwd=REPO_ROOT,
        env=env,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated-dir", default=str(DEFAULT_GENERATED_DIR))
    parser.add_argument("--base-port", type=int, default=4200)
    parser.add_argument("--runtime-port", type=int, default=9305)
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--log-level", default="warning")
    parser.add_argument("--database-url", default="postgresql://anip:anip@localhost:5454/anip_gtm")
    parser.add_argument("--no-runtime", action="store_true")
    args = parser.parse_args()

    processes = _start_services(args)
    time.sleep(2)
    if not args.no_runtime:
        processes.append(_start_runtime(args))

    def stop(_signum: int | None = None, _frame: object | None = None) -> None:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    print(
        json.dumps(
            {
                "status": "started",
                "runtime_url": None if args.no_runtime else f"http://127.0.0.1:{args.runtime_port}",
                "services": _service_config(args.base_port),
            },
            indent=2,
        ),
        flush=True,
    )
    try:
        while all(process.poll() is None for process in processes):
            time.sleep(1)
    finally:
        stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
