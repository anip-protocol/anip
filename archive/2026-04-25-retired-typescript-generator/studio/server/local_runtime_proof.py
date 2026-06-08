from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "service"


def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:] if len(text) > limit else text


def _run_command(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return
    output = "\n".join(part for part in [result.stdout, result.stderr] if part).strip()
    raise RuntimeError(f"{' '.join(command)} failed:\n{_tail(output)}")


def _http_json(method: str, url: str, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(url, data=data, method=method.upper())
    request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method.upper()} {url} failed ({exc.code}): {_tail(payload)}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method.upper()} {url} failed: {exc}") from exc


def _wait_for_service(base_url: str, timeout_seconds: int = 30) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            return _http_json("GET", f"{base_url}/.well-known/anip")
        except Exception as exc:  # pragma: no cover - exercised through polling path
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"Generated service did not become ready at {base_url}: {last_error}")


def _find_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _extract_generated_project_files(generation_run: dict[str, Any]) -> dict[str, str]:
    outputs = (((generation_run.get("data") or {}).get("outputs") or {}).get("runtime_target") or [])
    files: dict[str, str] = {}
    for item in outputs:
        if item.get("kind") != "generated_typescript_service_project_file":
            continue
        path = str(item.get("filename") or "").strip()
        if not path.startswith("typescript-service/"):
            continue
        relative_path = path.removeprefix("typescript-service/").strip()
        if not relative_path:
            continue
        files[relative_path] = str(item.get("content") or "")
    if not files:
        raise RuntimeError("Selected generation run does not contain a generated TypeScript service project bundle.")
    return files


def _parse_generated_capability_metadata(files: dict[str, str]) -> list[dict[str, Any]]:
    runtime_target_source = files.get("src/generated/runtime-target.ts")
    if not runtime_target_source:
        raise RuntimeError("Generated project bundle is missing src/generated/runtime-target.ts.")
    match = re.search(
        r"export const generatedCapabilityMetadata: GeneratedCapabilityRuntimeMetadata\[\] = (\[.*?\]);\s*$",
        runtime_target_source,
        re.DOTALL | re.MULTILINE,
    )
    if not match:
        raise RuntimeError("Could not parse generated capability metadata from runtime-target.ts.")
    return json.loads(match.group(1))


def _pick_proof_capability(capabilities: list[dict[str, Any]]) -> dict[str, Any]:
    if not capabilities:
        raise RuntimeError("Generated project bundle does not declare any capabilities.")
    for capability in capabilities:
        sample_parameters = capability.get("sample_parameters")
        if isinstance(sample_parameters, dict):
            return capability
    return capabilities[0]


def _build_observed_metadata(
    *,
    base_url: str,
    generation_run_artifact_id: str,
    generation_dependency_source: str | None,
    discovery_doc: dict[str, Any],
    manifest_doc: dict[str, Any],
) -> dict[str, Any]:
    discovery = discovery_doc.get("anip_discovery") if isinstance(discovery_doc.get("anip_discovery"), dict) else discovery_doc
    manifest = manifest_doc.get("raw") if isinstance(manifest_doc.get("raw"), dict) else manifest_doc
    service_identity = manifest.get("service_identity") if isinstance(manifest.get("service_identity"), dict) else {}
    discovery_capabilities = discovery.get("capabilities") if isinstance(discovery.get("capabilities"), dict) else {}
    manifest_capabilities = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), dict) else {}
    capability_ids = sorted(set(discovery_capabilities.keys()) | set(manifest_capabilities.keys()))
    capabilities: list[dict[str, Any]] = []
    for capability_id in capability_ids:
        manifest_capability = manifest_capabilities.get(capability_id) if isinstance(manifest_capabilities.get(capability_id), dict) else {}
        discovery_capability = discovery_capabilities.get(capability_id) if isinstance(discovery_capabilities.get(capability_id), dict) else {}
        minimum_scope = []
        for value in [
            manifest_capability.get("minimum_scope"),
            discovery_capability.get("minimum_scope"),
        ]:
            if isinstance(value, list):
                minimum_scope.extend(str(item) for item in value if str(item).strip())
        side_effect = manifest_capability.get("side_effect") or discovery_capability.get("side_effect") or {}
        side_effect_type = side_effect.get("type") if isinstance(side_effect, dict) else side_effect
        capabilities.append(
            {
                "id": capability_id,
                "minimum_scope": sorted(set(minimum_scope)),
                "side_effect_type": str(side_effect_type or "read"),
            }
        )

    return {
        "source": "inspect_discovery_manifest",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "generation_run_artifact_id": generation_run_artifact_id,
        "generation_dependency_source": generation_dependency_source,
        "service_id": str(service_identity.get("service_id") or discovery.get("service_id") or "generated-anip-service"),
        "base_url": base_url,
        "protocol": str(discovery.get("protocol") or manifest.get("manifest_version") or "anip/0.22"),
        "profile": str(discovery.get("profile") or "anip-compliant"),
        "compliance": str(discovery.get("compliance") or "generated_local_runtime_probe"),
        "trust_level": str((manifest.get("trust") or {}).get("level") or "signed"),
        "signature_present": bool((manifest.get("service_identity") or {}).get("signature")),
        "manifest_version": str(manifest.get("manifest_version") or "anip/0.22"),
        "jwks_uri_present": bool(discovery.get("jwks_uri")),
        "capabilities": capabilities,
    }


@dataclass
class LocalRuntimeProofResult:
    proof_generated_at: str
    base_url: str
    generation_run_artifact_id: str
    generation_dependency_source: str | None
    observed_service_metadata: dict[str, Any]
    invoked_capability_id: str
    invoke_response: dict[str, Any]
    execution_status: str | None


def run_generation_run_local_proof(generation_run_artifact: dict[str, Any]) -> LocalRuntimeProofResult:
    files = _extract_generated_project_files(generation_run_artifact)
    capabilities = _parse_generated_capability_metadata(files)
    proof_capability = _pick_proof_capability(capabilities)
    proof_generated_at = datetime.now(timezone.utc).isoformat()
    generation_data = generation_run_artifact.get("data") or {}
    generation_run_artifact_id = str(generation_run_artifact.get("id") or "")
    generation_dependency_source = (generation_data.get("generator_inputs") or {}).get("dependency_source")

    with TemporaryDirectory(prefix="anip-local-proof-") as temp_dir:
        project_dir = Path(temp_dir) / "typescript-service"
        project_dir.mkdir(parents=True, exist_ok=True)
        for relative_path, content in files.items():
            destination = project_dir / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")

        _run_command(["npm", "install", "--prefer-offline"], cwd=project_dir)
        _run_command(["npm", "run", "build"], cwd=project_dir)
        _run_command(["npm", "test"], cwd=project_dir)

        port = _find_free_port()
        base_url = f"http://127.0.0.1:{port}"
        log_path = project_dir / "local-proof.log"
        with log_path.open("w+", encoding="utf-8") as log_handle:
            process = subprocess.Popen(
                ["npm", "run", "start"],
                cwd=str(project_dir),
                env={
                    **os.environ,
                    "PORT": str(port),
                    "ANIP_API_KEYS_JSON": json.dumps({"dev-admin-key": "human:local-developer"}),
                },
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                discovery_doc = _wait_for_service(base_url)
                manifest_doc = _http_json("GET", f"{base_url}/anip/manifest")
                token_doc = _http_json(
                    "POST",
                    f"{base_url}/anip/tokens",
                    {
                        "capability": proof_capability["capability_id"],
                        "scope": proof_capability.get("minimum_scope") or [proof_capability["capability_id"]],
                        "subject": "studio-local-proof",
                    },
                    headers={"Authorization": "Bearer dev-admin-key"},
                )
                token = str(token_doc.get("token") or "")
                if not token:
                    raise RuntimeError("Generated local proof run did not return a bearer token.")
                invoke_response = _http_json(
                    "POST",
                    f"{base_url}/anip/invoke/{proof_capability['capability_id']}",
                    {"parameters": proof_capability.get("sample_parameters") or {}},
                    headers={"Authorization": f"Bearer {token}"},
                )
            except Exception as exc:
                log_handle.flush()
                log_output = log_path.read_text(encoding="utf-8")
                raise RuntimeError(f"{exc}\n\nGenerated runtime log:\n{_tail(log_output)}") from exc
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:  # pragma: no cover - defensive cleanup
                    process.kill()
                    process.wait(timeout=5)

    observed_service_metadata = _build_observed_metadata(
        base_url=base_url,
        generation_run_artifact_id=generation_run_artifact_id,
        generation_dependency_source=str(generation_dependency_source) if generation_dependency_source else None,
        discovery_doc=discovery_doc,
        manifest_doc=manifest_doc,
    )
    result_payload = invoke_response.get("result") if isinstance(invoke_response.get("result"), dict) else {}
    execution_status = result_payload.get("execution_status")

    return LocalRuntimeProofResult(
        proof_generated_at=proof_generated_at,
        base_url=base_url,
        generation_run_artifact_id=generation_run_artifact_id,
        generation_dependency_source=str(generation_dependency_source) if generation_dependency_source else None,
        observed_service_metadata=observed_service_metadata,
        invoked_capability_id=str(proof_capability.get("capability_id") or ""),
        invoke_response=invoke_response,
        execution_status=str(execution_status) if execution_status is not None else None,
    )
