from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib import error, parse, request


def env(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    return value or default


STUDIO_API_URL = env("STUDIO_API_URL", "http://gtm-studio-api:8100")
SERVICE_BASE_URL = env("OBSERVED_SERVICE_BASE_URL", "http://gtm-pipeline-service:9200")
PROJECT_ID = env("STUDIO_PROJECT_ID", "gtm-pipeline-q2-review")
SERVICE_ID = env("OBSERVED_SERVICE_ID", "anip-gtm-pipeline-showcase")
TIMEOUT_SECONDS = float(env("OBSERVE_TIMEOUT_SECONDS", "60"))
POLL_SECONDS = float(env("OBSERVE_POLL_SECONDS", "2"))


def slug_part(value: str) -> str:
    chars: list[str] = []
    previous_dash = False
    for char in value.strip().lower():
        if char.isalnum():
            chars.append(char)
            previous_dash = False
            continue
        if not previous_dash:
            chars.append("-")
            previous_dash = True
    return "".join(chars).strip("-")[:80] or "service"


def unique_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, list):
            for item in value:
                text = str(item).strip()
                if text and text not in seen:
                    seen.add(text)
                    output.append(text)
            continue
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return output


def first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def truthy_keys(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    return [str(key).strip() for key, enabled in value.items() if enabled not in (False, None)]


def http_json(method: str, url: str, payload: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, method=method.upper(), headers=headers, data=body)
    with request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        resp_headers = {str(key).lower(): str(value) for key, value in resp.headers.items()}
        return data, resp_headers


def wait_for_json(method: str, url: str, payload: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    deadline = time.time() + TIMEOUT_SECONDS
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            return http_json(method, url, payload)
        except Exception as exc:  # pragma: no cover - exercised in runtime, not unit tests
            last_error = exc
            time.sleep(POLL_SECONDS)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}") from last_error


def normalize_capability(capability_id: str, discovery_cap: dict[str, Any], manifest_cap: dict[str, Any]) -> dict[str, Any]:
    side_effect = first_string(
        manifest_cap.get("side_effect", {}).get("type") if isinstance(manifest_cap.get("side_effect"), dict) else manifest_cap.get("side_effect"),
        discovery_cap.get("side_effect", {}).get("type") if isinstance(discovery_cap.get("side_effect"), dict) else discovery_cap.get("side_effect"),
    )
    contract = first_string(
        manifest_cap.get("contract"),
        manifest_cap.get("contract_version"),
        discovery_cap.get("contract"),
    )
    cross_service = manifest_cap.get("cross_service") if isinstance(manifest_cap.get("cross_service"), dict) else {}
    control_requirements = manifest_cap.get("control_requirements")
    if isinstance(control_requirements, dict):
        control_requirements = truthy_keys(control_requirements)
    elif not isinstance(control_requirements, list):
        control_requirements = []

    financial = bool(discovery_cap.get("financial"))
    if isinstance(manifest_cap.get("cost"), dict) and manifest_cap["cost"].get("financial") is not None:
        financial = True

    return {
        "id": capability_id,
        "side_effect": side_effect,
        "minimum_scope": unique_strings([
            discovery_cap.get("minimum_scope"),
            manifest_cap.get("minimum_scope"),
        ]),
        "financial": financial,
        "contract": contract,
        "requires_binding": unique_strings([
            discovery_cap.get("requires_binding"),
            manifest_cap.get("requires_binding"),
        ]),
        "control_requirements": unique_strings([control_requirements]),
        "refresh_via": unique_strings([manifest_cap.get("refresh_via"), cross_service.get("refresh_via")]),
        "verify_via": unique_strings([manifest_cap.get("verify_via"), cross_service.get("verify_via")]),
        "followup_via": unique_strings([manifest_cap.get("followup_via"), cross_service.get("followup_via")]),
        "cross_service_handoff": unique_strings([cross_service.get("handoff_to")]),
        "cross_service_refresh": unique_strings([cross_service.get("refresh_via")]),
        "cross_service_verify": unique_strings([cross_service.get("verify_via")]),
        "cross_service_followup": unique_strings([cross_service.get("followup_via")]),
    }


def normalize_observed_metadata(discovery_doc: dict[str, Any], manifest_doc: dict[str, Any], manifest_headers: dict[str, str]) -> dict[str, Any]:
    discovery = discovery_doc.get("anip_discovery", discovery_doc)
    manifest = manifest_doc.get("manifest", manifest_doc)

    discovery_caps = discovery.get("capabilities") if isinstance(discovery.get("capabilities"), dict) else {}
    manifest_caps = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), dict) else {}
    capability_ids = unique_strings([list(discovery_caps.keys()), list(manifest_caps.keys())])

    profile = discovery.get("profile")
    if isinstance(profile, dict):
        profile = first_string(profile.get("core")) or json.dumps(profile, sort_keys=True)

    manifest_metadata = manifest.get("manifest_metadata") if isinstance(manifest.get("manifest_metadata"), dict) else {}
    service_identity = manifest.get("service_identity") if isinstance(manifest.get("service_identity"), dict) else {}
    posture = discovery.get("posture") if isinstance(discovery.get("posture"), dict) else {}

    return {
        "source": "inspect_discovery_manifest",
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "service_id": first_string(service_identity.get("id"), SERVICE_ID),
        "base_url": first_string(discovery.get("base_url"), SERVICE_BASE_URL),
        "protocol": first_string(manifest.get("protocol"), discovery.get("protocol")),
        "profile": first_string(profile),
        "compliance": first_string(discovery.get("compliance")),
        "trust_level": first_string(discovery.get("trust_level"), manifest.get("trust", {}).get("level")),
        "audit_retention": first_string(posture.get("audit", {}).get("retention")),
        "failure_detail_level": first_string(posture.get("failure_disclosure", {}).get("detail_level")),
        "anchoring_enabled": posture.get("anchoring", {}).get("enabled"),
        "signature_present": bool(manifest_headers.get("x-anip-signature")),
        "manifest_version": first_string(manifest_metadata.get("version")),
        "issuer_mode": first_string(service_identity.get("issuer_mode")),
        "jwks_uri_present": bool(first_string(service_identity.get("jwks_uri"))),
        "capabilities": [
            normalize_capability(capability_id, discovery_caps.get(capability_id, {}), manifest_caps.get(capability_id, {}))
            for capability_id in capability_ids
        ],
    }


def upsert_service_metadata(observed: dict[str, Any]) -> None:
    artifact_id = f"service-metadata-{slug_part(observed.get('service_id') or observed.get('base_url') or 'service')}"
    title = f"Observed Service Metadata: {observed.get('service_id') or observed.get('base_url') or 'Connected Service'}"
    list_url = f"{STUDIO_API_URL}/api/projects/{parse.quote(PROJECT_ID)}/service-metadata"
    existing, _ = wait_for_json("GET", list_url)
    existing_artifact = next((item for item in existing if item.get("id") == artifact_id), None)

    if existing_artifact:
      payload = {"title": title, "status": "active", "data": observed}
      update_url = f"{list_url}/{parse.quote(artifact_id)}"
      http_json("PUT", update_url, payload)
      print(f"Updated Studio service metadata artifact {artifact_id}")
      return

    payload = {"id": artifact_id, "title": title, "data": observed}
    http_json("POST", list_url, payload)
    print(f"Created Studio service metadata artifact {artifact_id}")


def main() -> int:
    wait_for_json("GET", f"{STUDIO_API_URL}/api/health")
    discovery_doc, _ = wait_for_json("GET", f"{SERVICE_BASE_URL}/.well-known/anip")
    manifest_doc, manifest_headers = wait_for_json("GET", f"{SERVICE_BASE_URL}/anip/manifest")
    observed = normalize_observed_metadata(discovery_doc, manifest_doc, manifest_headers)
    upsert_service_metadata(observed)
    print(json.dumps(observed, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP error {exc.code}: {detail}", file=sys.stderr)
        raise
