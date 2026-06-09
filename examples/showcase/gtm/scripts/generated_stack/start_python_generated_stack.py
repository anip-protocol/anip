"""Start the GTM Python-generated language-parity stack.

This starts the generator-produced Python ANIP services from
``output/gtm-language-parity/python``. It intentionally does not use the
handwritten GTM Python service apps, which are retained only as a reference
implementation.
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
DEFAULT_GENERATED_DIR = REPO_ROOT / "output" / "gtm-language-parity" / "python"
START_RUNTIME = REPO_ROOT / "examples" / "showcase" / "gtm" / "scripts" / "start_generated_llm_runtime.py"
RUNTIME_MODULE = "gtm_operator_contract_20260512235040"
SERVICE_MODULES = [
    ("pipeline", "gtm-pipeline-service", f"{RUNTIME_MODULE}.app:app"),
    ("enrichment", "gtm-enrichment-service", f"{RUNTIME_MODULE}.services.gtm_enrichment_service.app:app"),
    ("prioritization", "gtm-prioritization-service", f"{RUNTIME_MODULE}.services.gtm_prioritization_service.app:app"),
    ("outreach", "gtm-outreach-service", f"{RUNTIME_MODULE}.services.gtm_outreach_service.app:app"),
]


def _api_keys_json(generated_dir: Path) -> str:
    sys.path.insert(0, str(generated_dir / "src"))
    from gtm_operator_contract_20260512235040.runtime.actor import actor_profiles, encode_actor_principal

    return json.dumps({profile.api_key: encode_actor_principal(profile) for profile in actor_profiles().values()})


def _pythonpath(generated_dir: Path) -> str:
    paths = [
        str(generated_dir / "src"),
        str(REPO_ROOT / "packages" / "python" / "anip-crypto" / "src"),
        str(REPO_ROOT / "packages" / "python" / "anip-core" / "src"),
        str(REPO_ROOT / "packages" / "python" / "anip-service" / "src"),
        str(REPO_ROOT / "packages" / "python" / "anip-fastapi" / "src"),
        str(REPO_ROOT),
    ]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    return os.pathsep.join(paths)


def _ensure_key_file(generated_dir: Path) -> None:
    sys.path.insert(0, str(REPO_ROOT / "packages" / "python" / "anip-crypto" / "src"))
    from anip_crypto import KeyManager

    key_path = generated_dir / "anip-keys"
    if key_path.exists():
        try:
            json.loads(key_path.read_text())
            return
        except json.JSONDecodeError:
            key_path.unlink()
    KeyManager(str(key_path))


def _service_config(base_port: int) -> list[dict[str, str]]:
    services: list[dict[str, str]] = []
    for index, (name, _service_id, _module) in enumerate(SERVICE_MODULES):
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
    _ensure_key_file(generated_dir)
    api_keys = _api_keys_json(generated_dir)
    processes: list[subprocess.Popen[bytes]] = []
    for index, (_name, service_id, module) in enumerate(SERVICE_MODULES):
        env = os.environ.copy()
        env.update(
            {
                "PYTHONPATH": _pythonpath(generated_dir),
                "ANIP_API_KEYS_JSON": api_keys,
                "DATABASE_URL": args.database_url,
                "PORT": str(args.base_port + index),
                "ANIP_SERVICE_ID": service_id,
            }
        )
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    module,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.base_port + index),
                    "--log-level",
                    args.service_log_level,
                ],
                cwd=generated_dir,
                env=env,
            )
        )
    return processes


def _start_runtime(args: argparse.Namespace) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(REPO_ROOT),
            "ANIP_AGENT_APP_MODULE": "gtm_agent_app",
            "OPENAI_MODEL": args.model,
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
            args.runtime_log_level,
        ],
        cwd=REPO_ROOT,
        env=env,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated-dir", default=str(DEFAULT_GENERATED_DIR))
    parser.add_argument("--base-port", type=int, default=4300)
    parser.add_argument("--runtime-port", type=int, default=9306)
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--service-log-level", default="warning")
    parser.add_argument("--runtime-log-level", default="warning")
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
                "reference_python_stack": "not used",
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
