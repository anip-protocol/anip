"""Registry-backed verifier provenance endpoints."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_pool
from .. import repository
from ..repository import NotFoundError

router = APIRouter(prefix="/api/projects/{pid}/registry-verification", tags=["registry_verification"])
ROOT = Path(__file__).resolve().parents[3]
GO_PACKAGES_DIR = ROOT / "packages" / "go"
_REGISTRY_CONFIG_KEY = "registry_trust_policy_config"


class RegistryGoVerificationRequest(BaseModel):
    package_id: str
    package_version: str
    registry_url: str | None = None
    publication_artifact_id: str | None = None


def _load_persisted_registry_trust_policy() -> dict[str, Any]:
    try:
        with get_pool().connection() as conn:
            row = conn.execute(
                "SELECT value FROM studio_settings WHERE key = %s",
                (_REGISTRY_CONFIG_KEY,),
            ).fetchone()
    except Exception:
        return {}
    if not row:
        return {}
    value = row.get("value")
    return value if isinstance(value, dict) else {}


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_registry_mode(value: Any) -> str | None:
    normalized = _normalize_optional_string(value)
    if normalized is None:
        return None
    normalized = normalized.lower()
    return normalized if normalized in {"dev", "production"} else None


def _default_registry_url() -> str:
    stored = _load_persisted_registry_trust_policy()
    return (
        _normalize_optional_string(os.environ.get("STUDIO_REGISTRY_URL"))
        or _normalize_optional_string(os.environ.get("VITE_REGISTRY_BACKEND_URL"))
        or _normalize_optional_string(stored.get("registry_url"))
        or "http://127.0.0.1:8200"
    ).rstrip("/")


def _default_required_registry_mode() -> str | None:
    stored = _load_persisted_registry_trust_policy()
    configured = _normalize_registry_mode(os.environ.get("STUDIO_REGISTRY_REQUIRED_MODE"))
    if configured:
        return configured
    stored_mode = _normalize_registry_mode(stored.get("required_registry_mode"))
    if stored_mode:
        return stored_mode
    studio_mode = (
        os.environ.get("STUDIO_MODE")
        or os.environ.get("APP_ENV")
        or os.environ.get("ENVIRONMENT")
        or ""
    ).strip().lower()
    if studio_mode == "production":
        return "production"
    return None


def _trusted_registry_key_id() -> str | None:
    stored = _load_persisted_registry_trust_policy()
    return (
        _normalize_optional_string(os.environ.get("STUDIO_REGISTRY_TRUSTED_KEY_ID"))
        or _normalize_optional_string(stored.get("trusted_registry_key_id"))
    )


def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:] if len(text) > limit else text


def _run_go_verifier_for_registry(
    package_id: str,
    package_version: str,
    registry_url: str,
    required_registry_mode: str | None = None,
    trusted_registry_key_id: str | None = None,
) -> dict[str, Any]:
    command = [
        "go",
        "run",
        "./cmd/anip-verify",
        "--registry-url",
        registry_url,
        "--package-id",
        package_id,
        "--package-version",
        package_version,
    ]
    if required_registry_mode:
        command.extend(["--require-registry-mode", required_registry_mode])
    if trusted_registry_key_id:
        command.extend(["--trusted-registry-key-id", trusted_registry_key_id])
    result = subprocess.run(
        command,
        cwd=str(GO_PACKAGES_DIR),
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    output = "\n".join(part for part in [result.stdout, result.stderr] if part).strip()
    raise HTTPException(status_code=502, detail=f"verifier did not return JSON:\n{_tail(output)}")


def _registry_trust_posture(result: dict[str, Any]) -> dict[str, str]:
    checks = result.get("checks") if isinstance(result.get("checks"), list) else []
    policy_failures = [
        check.get("name", "registry_trust_policy")
        for check in checks
        if isinstance(check, dict)
        and str(check.get("name", "")).startswith("registry_trust_policy_")
        and check.get("status") == "fail"
    ]
    signing_mode = str(result.get("registry_signing_mode") or "").strip().lower()
    active_key_id = str(result.get("registry_active_key_id") or "").strip()

    if policy_failures:
        return {
            "label": "Untrusted / policy mismatch",
            "detail": "Registry verifier trust policy failed: " + ", ".join(policy_failures),
        }
    if signing_mode == "production":
        return {
            "label": "Trusted production Registry",
            "detail": f"Registry reports production signing mode with active key {active_key_id or 'not reported'}.",
        }
    if signing_mode == "dev":
        return {
            "label": "Development Registry",
            "detail": f"Registry reports development signing mode with active key {active_key_id or 'not reported'}.",
        }
    if signing_mode:
        return {
            "label": f"{signing_mode} Registry",
            "detail": f"Registry reports signing mode {signing_mode} with active key {active_key_id or 'not reported'}.",
        }
    return {
        "label": "Registry signing posture not reported",
        "detail": "Verifier output did not include Registry signing mode metadata.",
    }


def _revision_matches(actual: dict[str, Any] | None, expected: dict[str, Any] | None) -> bool | None:
    if not actual or not expected:
        return None
    if actual.get("artifact_id") and expected.get("artifact_id"):
        return actual.get("artifact_id") == expected.get("artifact_id")
    if actual.get("ref") and expected.get("ref"):
        return actual.get("ref") == expected.get("ref")
    if actual.get("revision_number") is not None and expected.get("revision_number") is not None:
        return actual.get("revision_number") == expected.get("revision_number")
    return None


def _format_revision_label(kind: str, revision: dict[str, Any] | None) -> str:
    if not revision:
        return f"{kind} revision not recorded"
    ref = revision.get("ref") or revision.get("artifact_id")
    revision_number = revision.get("revision_number")
    if revision_number is not None and ref:
        return f"{kind} r{revision_number} ({ref})"
    if revision_number is not None:
        return f"{kind} r{revision_number}"
    return ref or f"{kind} revision not recorded"


def _publication_context(publication_artifact: dict[str, Any] | None) -> dict[str, Any]:
    data = (publication_artifact or {}).get("data") or {}
    package_record = data.get("package") or {}
    lineage = data.get("lineage") or package_record.get("lineage") or package_record.get("manifest", {}).get("lineage") or package_record.get("recommended_lock", {}).get("lineage") or {}
    receipt = data.get("receipt") or {}
    return {
        "artifact_id": (publication_artifact or {}).get("id"),
        "package": package_record,
        "receipt": receipt,
        "product_revision": lineage.get("product_revision") if isinstance(lineage, dict) else None,
        "developer_revision": lineage.get("developer_revision") if isinstance(lineage, dict) else None,
    }


def _summarize_go_registry_result(
    result: dict[str, Any],
    package_id: str,
    package_version: str,
    publication_artifact: dict[str, Any] | None,
) -> dict[str, Any]:
    context = _publication_context(publication_artifact)
    expected_package = context["package"] or {}
    expected_receipt = context["receipt"] or {}
    expected_product = context["product_revision"]
    expected_developer = context["developer_revision"]
    actual_product = result.get("product_revision") or (result.get("lineage") or {}).get("product_revision")
    actual_developer = result.get("developer_revision") or (result.get("lineage") or {}).get("developer_revision")
    actual_package_id = result.get("package_id")
    actual_package_version = result.get("package_version")
    package_label = f"{actual_package_id or package_id}@{actual_package_version or package_version}"
    receipt_signature = result.get("registry_receipt_signature") or result.get("receipt_signature") or "Not recorded"
    receipt_status = result.get("receipt_status") or ("none" if receipt_signature == "Not recorded" else "present")
    registry_signing_mode = result.get("registry_signing_mode")
    registry_active_key_id = result.get("registry_active_key_id")
    registry_trust_posture = _registry_trust_posture(result)
    target_package_matches = actual_package_id == package_id and actual_package_version == package_version
    artifact_package_matches = not expected_package or (
        actual_package_id == expected_package.get("package_id")
        and actual_package_version == expected_package.get("package_version")
    )
    receipt_matches = (
        receipt_signature == "Not recorded"
        or not expected_receipt.get("registry_signature")
        or receipt_signature == expected_receipt.get("registry_signature")
    )
    product_matches = _revision_matches(actual_product, expected_product)
    developer_matches = _revision_matches(actual_developer, expected_developer)

    status = "aligned"
    label = "CLI result aligned"
    detail = "The verifier result matches the remote Registry package and recorded Studio publication lineage."
    if result.get("status") != "ok":
        status = "mismatch"
        label = "CLI result mismatch"
        detail = "verifier reported a non-passing status."
    elif not target_package_matches or not artifact_package_matches:
        status = "mismatch"
        label = "CLI result mismatch"
        detail = "verifier package identity does not match the requested Registry package or Studio publication artifact."
    elif receipt_status == "failed" or not receipt_matches:
        status = "mismatch"
        label = "CLI result mismatch"
        detail = "verifier receipt state does not match the Studio publication receipt."
    elif product_matches is False or developer_matches is False:
        status = "mismatch"
        label = "CLI result mismatch"
        detail = "verifier revision lineage does not match the Studio publication lineage."
    elif publication_artifact and (product_matches is None or developer_matches is None):
        status = "incomplete"
        label = "CLI provenance incomplete"
        detail = "Package identity matches, but the verifier output does not include enough Product/Developer revision lineage to prove it is the same publication lineage."

    return {
        "status": status,
        "label": label,
        "detail": detail,
        "sourceTool": "anip-verify",
        "packageLabel": package_label,
        "receiptStatus": receipt_status,
        "receiptSignature": receipt_signature,
        "registrySigningMode": registry_signing_mode,
        "registryActiveKeyID": registry_active_key_id,
        "registryTrustPostureLabel": registry_trust_posture["label"],
        "registryTrustPostureDetail": registry_trust_posture["detail"],
        "productRevisionLabel": _format_revision_label("Product", actual_product),
        "developerRevisionLabel": _format_revision_label("Developer", actual_developer),
        "matchedPublicationArtifactId": context["artifact_id"],
    }


@router.post("/verify/go")
def verify_registry_publication_with_go(pid: str, body: RegistryGoVerificationRequest):
    package_id = body.package_id.strip()
    package_version = body.package_version.strip()
    if not package_id or not package_version:
        raise HTTPException(status_code=422, detail="package_id and package_version are required")
    registry_url = (body.registry_url or _default_registry_url()).rstrip("/")

    publication_artifact = None
    if body.publication_artifact_id:
        with get_pool().connection() as conn:
            try:
                publication_artifact = repository.get_pm_artifact(conn, pid, body.publication_artifact_id)
            except NotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc))

    required_registry_mode = _default_required_registry_mode()
    trusted_registry_key_id = _trusted_registry_key_id()
    raw_result = _run_go_verifier_for_registry(
        package_id,
        package_version,
        registry_url,
        required_registry_mode,
        trusted_registry_key_id,
    )
    summary = _summarize_go_registry_result(raw_result, package_id, package_version, publication_artifact)
    imported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    artifact_id = f"{pid}-go-registry-provenance-{int(time() * 1000)}"
    artifact_data = {
        "artifact_type": "external_cli_provenance_result",
        "imported_at": imported_at,
        "source_tool": "anip-verify",
        "raw_result": raw_result,
        "summary": summary,
        "registry_url": registry_url,
        "registry_trust_policy": {
            "required_registry_mode": required_registry_mode,
            "trusted_registry_key_id": trusted_registry_key_id,
        },
        "reconciled_against_publication_artifact_id": summary["matchedPublicationArtifactId"],
    }
    with get_pool().connection() as conn:
        try:
            artifact = repository.create_pm_artifact(
                conn,
                project_id=pid,
                artifact_id=artifact_id,
                title=f"Registry Verifier Provenance {summary['packageLabel']}",
                data=artifact_data,
            )
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
    return {
        "artifact": artifact,
        "raw_result": raw_result,
        "summary": summary,
        "registry_url": registry_url,
        "registry_trust_policy": artifact_data["registry_trust_policy"],
    }
