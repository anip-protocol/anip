"""Studio-local immutable publication records."""

from __future__ import annotations

import json
import hashlib
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..db import get_pool
from .. import repository
from ..repository import LocalPublicationExistsError, NotFoundError
from ..publication_guard import validate_publication_saved_revision
from ..runtime_paths import repo_root

router = APIRouter(prefix="/api/projects/{pid}/local-publications", tags=["local_publications"])
ROOT = repo_root()
GO_PACKAGES_DIR = ROOT / "packages" / "go"
CURRENT_ANIP_SPEC_VERSION = "anip/0.24"


class LocalPublicationRequest(BaseModel):
    package_id: str
    package_version: str
    project_ref: str
    product_revision_ref: str
    developer_revision_ref: str
    contract_signature: str
    lineage: dict[str, Any] | None = None
    schema_version: str = "anip-service-definition/v1"
    manifest: dict[str, Any] = Field(default_factory=dict)
    service_definition: dict[str, Any] = Field(default_factory=dict)
    recommended_lock: dict[str, Any] = Field(default_factory=dict)
    readme: str | None = None
    source_links: list[dict[str, str]] = Field(default_factory=list)
    implementation_materials: list[dict[str, str]] = Field(default_factory=list)


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "detail": detail,
    }


def _require_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail=f"{field_name} is required")
    return text


def _digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _implementation_materials_from_manifest(manifest: dict[str, Any]) -> list[dict[str, str]]:
    raw = manifest.get("implementation_materials") or manifest.get("implementation_material")
    if isinstance(raw, dict):
        raw = raw.get("custom_code_bundles") or [raw]
    if not isinstance(raw, list):
        return []
    items: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or item.get("uri") or item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        bundle_tree_sha256 = str(item.get("bundle_tree_sha256") or item.get("tree_sha256") or "").strip()
        if ref or title or bundle_tree_sha256:
            material: dict[str, str] = {"ref": ref}
            if title:
                material["title"] = title
            if bundle_tree_sha256:
                material["bundle_tree_sha256"] = bundle_tree_sha256
            items.append(material)
    return items


def _normalize_implementation_materials(materials: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in materials:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or "").strip()
        title = str(item.get("title") or "").strip()
        bundle_tree_sha256 = str(item.get("bundle_tree_sha256") or "").strip().lower()
        if not (ref or title or bundle_tree_sha256):
            continue
        material: dict[str, str] = {"ref": ref}
        if title:
            material["title"] = title
        if bundle_tree_sha256:
            material["bundle_tree_sha256"] = bundle_tree_sha256
        normalized.append(material)
    return normalized


def _without_package_execution_signature(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            key: _without_package_execution_signature(value)
            for key, value in payload.items()
            if key != "package_execution_signature"
        }
    if isinstance(payload, list):
        return [_without_package_execution_signature(item) for item in payload]
    return payload


def _definition_capability_ids(service_definition: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    capabilities = service_definition.get("capability_formalizations")
    if not isinstance(capabilities, list):
        return ids
    for capability in capabilities:
        if not isinstance(capability, dict):
            continue
        capability_id = str(capability.get("capability_id") or "").strip()
        if capability_id:
            ids.add(capability_id)
    return ids


def _agent_consumability_capability_ids(agent_consumability: dict[str, Any]) -> set[str]:
    capabilities = agent_consumability.get("capabilities")
    if not isinstance(capabilities, dict):
        return set()
    return {str(capability_id).strip() for capability_id in capabilities.keys() if str(capability_id).strip()}


def _number(value: Any) -> float:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0


def _execution_metadata_checks(
    manifest: dict[str, Any],
    service_definition: dict[str, Any],
    lock: dict[str, Any],
    implementation_materials: list[dict[str, str]],
    lineage: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    agent_consumability = manifest.get("agent_consumability")
    if not isinstance(agent_consumability, dict) or not agent_consumability:
        agent_consumability = lock.get("agent_consumability")
    if not isinstance(agent_consumability, dict):
        agent_consumability = {}

    readiness = manifest.get("agent_consumption_readiness")
    if not isinstance(readiness, dict) or not readiness:
        readiness = lock.get("agent_consumption_readiness")
    if not isinstance(readiness, dict):
        readiness = {}

    definition_ids = _definition_capability_ids(service_definition)
    consumability_ids = _agent_consumability_capability_ids(agent_consumability)
    readiness_summary = readiness.get("summary") if isinstance(readiness.get("summary"), dict) else {}
    observed_signature = str(
        manifest.get("package_execution_signature")
        or lock.get("package_execution_signature")
        or ""
    ).strip()
    computed_signature = _compute_package_execution_signature(
        manifest,
        service_definition,
        lock,
        implementation_materials,
        lineage or {},
    )

    return [
        _check(
            "agent_consumability_present",
            bool(agent_consumability),
            "agent_consumability metadata is required for executable packages",
        ),
        _check(
            "agent_consumability_schema_present",
            bool(str(agent_consumability.get("schema_version") or "").strip()),
            f"schema_version={agent_consumability.get('schema_version') or ''}",
        ),
        _check(
            "agent_consumability_capabilities_match_definition",
            bool(definition_ids) and definition_ids == consumability_ids,
            f"definition={sorted(definition_ids)} consumability={sorted(consumability_ids)}",
        ),
        _check(
            "agent_consumption_readiness_ready",
            str(readiness.get("status") or "").strip().lower() == "ready",
            f"status={readiness.get('status') or ''}",
        ),
        _check(
            "agent_consumption_readiness_has_no_blockers",
            _number(readiness_summary.get("blockers")) == 0,
            f"blockers={readiness_summary.get('blockers')}",
        ),
        _check(
            "agent_consumption_readiness_has_no_warnings",
            _number(readiness_summary.get("warnings")) == 0,
            f"warnings={readiness_summary.get('warnings')}",
        ),
        _check(
            "package_execution_signature_present",
            bool(observed_signature),
            f"signature={observed_signature}",
        ),
        _check(
            "package_execution_signature_matches",
            bool(observed_signature) and observed_signature == computed_signature,
            f"stored={observed_signature} computed={computed_signature}",
        ),
    ]


def _validate_execution_metadata(
    manifest: dict[str, Any],
    service_definition: dict[str, Any],
    lock: dict[str, Any],
    implementation_materials: list[dict[str, str]],
    lineage: dict[str, Any] | None = None,
    require_signature: bool = False,
) -> None:
    checks = _execution_metadata_checks(
        manifest,
        service_definition,
        lock,
        implementation_materials,
        lineage,
    )
    failures = [
        check
        for check in checks
        if check["status"] != "pass"
        and (require_signature or not check["name"].startswith("package_execution_signature_"))
    ]
    if failures:
        first = failures[0]
        raise HTTPException(status_code=422, detail=f"{first['name']}: {first['detail']}")


def _compute_package_execution_signature(
    manifest: dict[str, Any],
    service_definition: dict[str, Any],
    lock: dict[str, Any],
    implementation_materials: list[dict[str, str]],
    lineage: dict[str, Any] | None = None,
) -> str:
    payload = {
        "schema_version": "anip-package-execution-signature/v1",
        "service_definition": service_definition,
        "agent_consumability": _without_package_execution_signature(manifest).get("agent_consumability"),
        "agent_consumption_readiness": _without_package_execution_signature(manifest).get("agent_consumption_readiness"),
        "agent_consumption_publication_gate": _without_package_execution_signature(manifest).get("agent_consumption_publication_gate"),
        "implementation_materials": implementation_materials,
        "recommended_lock": _without_package_execution_signature(lock),
        "lineage": lineage or {},
    }
    return _digest(payload)


def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:] if len(text) > limit else text


def _build_local_publication(pid: str, body: LocalPublicationRequest) -> dict[str, Any]:
    package_id = _require_text(body.package_id, "package_id")
    package_version = _require_text(body.package_version, "package_version")
    project_ref = _require_text(body.project_ref, "project_ref")
    product_revision_ref = _require_text(body.product_revision_ref, "product_revision_ref")
    developer_revision_ref = _require_text(body.developer_revision_ref, "developer_revision_ref")
    contract_signature = _require_text(body.contract_signature, "contract_signature")
    schema_version = _require_text(body.schema_version, "schema_version")
    if schema_version != "anip-service-definition/v1":
        raise HTTPException(status_code=422, detail="schema_version must be anip-service-definition/v1")
    manifest_spec_version = str(body.manifest.get("anip_spec_version") or "").strip()
    if manifest_spec_version != CURRENT_ANIP_SPEC_VERSION:
        raise HTTPException(status_code=422, detail=f"manifest anip_spec_version must be {CURRENT_ANIP_SPEC_VERSION}")
    body.recommended_lock["anip_spec_version"] = CURRENT_ANIP_SPEC_VERSION
    readme = (body.readme or body.manifest.get("readme") or "").strip()
    source_links = body.source_links or body.manifest.get("source_links") or []
    implementation_materials = _normalize_implementation_materials(
        body.implementation_materials or _implementation_materials_from_manifest(body.manifest)
    )
    if readme:
        body.manifest["readme"] = readme
    if source_links:
        body.manifest["source_links"] = source_links
    if implementation_materials:
        body.manifest["implementation_material"] = {
            "custom_code_bundles": implementation_materials,
        }
    lineage = body.lineage or body.manifest.get("lineage") or body.recommended_lock.get("lineage") or {}
    _validate_execution_metadata(
        body.manifest,
        body.service_definition,
        body.recommended_lock,
        implementation_materials,
        lineage,
    )
    package_execution_signature = _compute_package_execution_signature(
        body.manifest,
        body.service_definition,
        body.recommended_lock,
        implementation_materials,
        lineage,
    )
    body.manifest["package_execution_signature"] = package_execution_signature
    body.recommended_lock["package_execution_signature"] = package_execution_signature
    published_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest_digest = _digest(body.manifest)
    definition_digest = _digest(body.service_definition)
    lock_digest = _digest(body.recommended_lock)

    package_record = {
        "package_id": package_id,
        "package_version": package_version,
        "project_ref": project_ref,
        "product_revision_ref": product_revision_ref,
        "developer_revision_ref": developer_revision_ref,
        "contract_signature": contract_signature,
        "lineage": lineage,
        "schema_version": schema_version,
        "manifest_digest": manifest_digest,
        "definition_digest": definition_digest,
        "lock_digest": lock_digest,
        "package_execution_signature": package_execution_signature,
        "published_at": published_at,
        "authority": "local-studio",
        "manifest": body.manifest,
        "service_definition": body.service_definition,
        "recommended_lock": body.recommended_lock,
        "readme": readme,
        "source_links": source_links,
        "implementation_materials": implementation_materials,
    }
    receipt_payload = {
        "authority": "local-studio",
        "package_id": package_id,
        "package_version": package_version,
        "contract_signature": contract_signature,
        "definition_digest": definition_digest,
        "manifest_digest": manifest_digest,
        "lock_digest": lock_digest,
        "package_execution_signature": package_execution_signature,
        "issued_at": published_at,
    }
    if lineage:
        receipt_payload["lineage"] = lineage
    receipt = {
        "receipt_id": _digest({
            "authority": "local-studio",
            "package_id": package_id,
            "package_version": package_version,
            "issued_at": published_at,
        }),
        "package_id": package_id,
        "package_version": package_version,
        "registry_signature": _digest(receipt_payload),
        "issued_at": published_at,
        "authority": "local-studio",
    }
    return {
        "publication_id": f"local-publication-{pid}-{package_id}-{package_version}".replace("/", "-"),
        "package_id": package_id,
        "package_version": package_version,
        "project_ref": project_ref,
        "product_revision_ref": product_revision_ref,
        "developer_revision_ref": developer_revision_ref,
        "contract_signature": contract_signature,
        "schema_version": schema_version,
        "manifest_digest": manifest_digest,
        "definition_digest": definition_digest,
        "package_record": package_record,
        "receipt": receipt,
    }


def _build_package_bundle(record: dict[str, Any]) -> dict[str, Any]:
    package_record = record.get("package") or {}
    receipt = record.get("receipt") or {}
    manifest = package_record.get("manifest") or {}
    service_definition = package_record.get("service_definition") or {}
    lock = package_record.get("recommended_lock") or {}
    return {
        "bundle_schema_version": "anip-package-bundle/v1",
        "authority": record.get("authority") or "local-studio",
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "publication": record.get("publication") or {},
        "package": package_record,
        "receipt": receipt,
        "lineage": package_record.get("lineage") or manifest.get("lineage") or lock.get("lineage") or {},
        "manifest": manifest,
        "service_definition": service_definition,
        "lock": lock,
        "digests": {
            "manifest": package_record.get("manifest_digest") or _digest(manifest),
            "service_definition": package_record.get("definition_digest") or _digest(service_definition),
            "lock": package_record.get("lock_digest") or _digest(lock),
            "package_execution": package_record.get("package_execution_signature")
            or manifest.get("package_execution_signature")
            or lock.get("package_execution_signature"),
            "receipt": receipt.get("registry_signature"),
        },
    }


def _verify_local_publication(record: dict[str, Any]) -> dict[str, Any]:
    package_record = record.get("package") or {}
    receipt = record.get("receipt") or {}
    manifest = package_record.get("manifest") or {}
    service_definition = package_record.get("service_definition") or {}
    lock = package_record.get("recommended_lock") or {}
    implementation_materials = _normalize_implementation_materials(package_record.get("implementation_materials") or [])
    authority = record.get("authority") or receipt.get("authority") or package_record.get("authority") or "local-studio"
    package_id = package_record.get("package_id") or record.get("publication", {}).get("package_id")
    package_version = package_record.get("package_version") or record.get("publication", {}).get("package_version")
    contract_signature = package_record.get("contract_signature") or record.get("publication", {}).get("contract_signature")
    issued_at = receipt.get("issued_at")
    lineage = package_record.get("lineage") or manifest.get("lineage") or package_record.get("recommended_lock", {}).get("lineage")

    computed_manifest_digest = _digest(manifest)
    computed_definition_digest = _digest(service_definition)
    computed_lock_digest = _digest(lock)
    computed_package_execution_signature = _compute_package_execution_signature(
        manifest,
        service_definition,
        lock,
        implementation_materials,
        lineage if isinstance(lineage, dict) else {},
    )
    stored_package_execution_signature = str(
        package_record.get("package_execution_signature")
        or manifest.get("package_execution_signature")
        or lock.get("package_execution_signature")
        or ""
    ).strip()
    expected_receipt_payload = {
        "authority": authority,
        "package_id": package_id,
        "package_version": package_version,
        "contract_signature": contract_signature,
        "definition_digest": computed_definition_digest,
        "manifest_digest": computed_manifest_digest,
        "lock_digest": computed_lock_digest,
        "package_execution_signature": stored_package_execution_signature,
        "issued_at": issued_at,
    }
    if lineage:
        expected_receipt_payload["lineage"] = lineage
    computed_receipt_signature = _digest(expected_receipt_payload)
    computed_receipt_id = _digest({
        "authority": authority,
        "package_id": package_id,
        "package_version": package_version,
        "issued_at": issued_at,
    })

    checks = [
        _check(
            "authority_is_local_studio",
            authority == "local-studio",
            f"authority={authority}",
        ),
        _check(
            "package_identity_present",
            bool(package_id and package_version),
            f"package={package_id}@{package_version}",
        ),
        _check(
            "contract_signature_present",
            bool(contract_signature),
            f"contract_signature={contract_signature or ''}",
        ),
        _check(
            "manifest_digest_matches",
            package_record.get("manifest_digest") == computed_manifest_digest,
            f"stored={package_record.get('manifest_digest')} computed={computed_manifest_digest}",
        ),
        _check(
            "definition_digest_matches",
            package_record.get("definition_digest") == computed_definition_digest,
            f"stored={package_record.get('definition_digest')} computed={computed_definition_digest}",
        ),
        _check(
            "lock_digest_matches",
            package_record.get("lock_digest") == computed_lock_digest,
            f"stored={package_record.get('lock_digest')} computed={computed_lock_digest}",
        ),
        *_execution_metadata_checks(
            manifest,
            service_definition,
            lock,
            implementation_materials,
            lineage if isinstance(lineage, dict) else {},
        ),
        _check(
            "package_record_execution_signature_matches",
            package_record.get("package_execution_signature") == stored_package_execution_signature,
            f"stored={package_record.get('package_execution_signature')} manifest_or_lock={stored_package_execution_signature}",
        ),
        _check(
            "computed_package_execution_signature_matches",
            stored_package_execution_signature == computed_package_execution_signature,
            f"stored={stored_package_execution_signature} computed={computed_package_execution_signature}",
        ),
        _check(
            "receipt_identity_matches",
            receipt.get("package_id") == package_id and receipt.get("package_version") == package_version,
            f"receipt={receipt.get('package_id')}@{receipt.get('package_version')} package={package_id}@{package_version}",
        ),
        _check(
            "receipt_id_matches",
            receipt.get("receipt_id") == computed_receipt_id,
            f"stored={receipt.get('receipt_id')} computed={computed_receipt_id}",
        ),
        _check(
            "receipt_signature_matches",
            receipt.get("registry_signature") == computed_receipt_signature,
            f"stored={receipt.get('registry_signature')} computed={computed_receipt_signature}",
        ),
    ]
    status = "ok" if all(check["status"] == "pass" for check in checks) else "failed"
    receipt_status = "verified" if status == "ok" else "failed"
    return {
        "status": status,
        "receipt_status": receipt_status,
        "authority": authority,
        "package_id": package_id,
        "package_version": package_version,
        "lineage": lineage or None,
        "product_revision": lineage.get("product_revision") if isinstance(lineage, dict) else None,
        "developer_revision": lineage.get("developer_revision") if isinstance(lineage, dict) else None,
        "definition_digest": computed_definition_digest,
        "manifest_digest": computed_manifest_digest,
        "lock_digest": computed_lock_digest,
        "package_execution_signature": stored_package_execution_signature,
        "receipt_signature": receipt.get("registry_signature"),
        "computed_receipt_signature": computed_receipt_signature,
        "checks": checks,
    }


def _run_go_verifier_for_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    with TemporaryDirectory(prefix="anip-go-verifier-") as temp_dir:
        bundle_path = Path(temp_dir) / "local-publication.anip-package.json"
        bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
        result = subprocess.run(
            ["go", "run", "./cmd/anip-verify", "--package-bundle", str(bundle_path)],
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


def _summarize_go_verifier_result(result: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    package_record = record.get("package") or {}
    receipt = record.get("receipt") or {}
    lineage = package_record.get("lineage") or package_record.get("manifest", {}).get("lineage") or package_record.get("recommended_lock", {}).get("lineage") or {}
    expected_product = lineage.get("product_revision") if isinstance(lineage, dict) else None
    expected_developer = lineage.get("developer_revision") if isinstance(lineage, dict) else None
    actual_product = result.get("product_revision") or (result.get("lineage") or {}).get("product_revision")
    actual_developer = result.get("developer_revision") or (result.get("lineage") or {}).get("developer_revision")
    package_id = result.get("package_id")
    package_version = result.get("package_version")
    package_label = f"{package_id or 'unknown-package'}@{package_version or 'unknown-version'}"
    receipt_signature = result.get("registry_receipt_signature") or result.get("receipt_signature") or "Not recorded"
    receipt_status = result.get("receipt_status") or ("none" if receipt_signature == "Not recorded" else "present")
    package_matches = package_id == package_record.get("package_id") and package_version == package_record.get("package_version")
    product_matches = _revision_matches(actual_product, expected_product)
    developer_matches = _revision_matches(actual_developer, expected_developer)
    receipt_matches = receipt_signature == "Not recorded" or not receipt.get("registry_signature") or receipt_signature == receipt.get("registry_signature")

    status = "aligned"
    label = "CLI result aligned"
    detail = "The verifier result matches Studio publication package identity, receipt state, and Product/Developer revision lineage."
    if result.get("status") != "ok":
        status = "mismatch"
        label = "CLI result mismatch"
        detail = "verifier reported a non-passing status."
    elif not package_matches:
        status = "mismatch"
        label = "CLI result mismatch"
        detail = "verifier package identity does not match the Studio local publication."
    elif receipt_status == "failed" or not receipt_matches:
        status = "mismatch"
        label = "CLI result mismatch"
        detail = "verifier receipt state does not match the Studio local publication receipt."
    elif product_matches is False or developer_matches is False:
        status = "mismatch"
        label = "CLI result mismatch"
        detail = "verifier revision lineage does not match the Studio local publication lineage."
    elif product_matches is None or developer_matches is None:
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
        "productRevisionLabel": _format_revision_label("Product", actual_product),
        "developerRevisionLabel": _format_revision_label("Developer", actual_developer),
        "matchedPublicationArtifactId": None,
    }


@router.get("")
def list_local_publications(pid: str):
    with get_pool().connection() as conn:
        try:
            return {"items": repository.list_local_publications(conn, pid)}
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{publication_id}")
def get_local_publication(pid: str, publication_id: str):
    with get_pool().connection() as conn:
        try:
            return repository.get_local_publication(conn, pid, publication_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{publication_id}/bundle")
def get_local_publication_bundle(pid: str, publication_id: str):
    with get_pool().connection() as conn:
        try:
            record = repository.get_local_publication(conn, pid, publication_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    bundle = _build_package_bundle(record)
    package_record = bundle["package"]
    filename = f"{package_record.get('package_id', publication_id)}-{package_record.get('package_version', 'bundle')}.anip-package.json".replace("/", "-")
    return JSONResponse(
        bundle,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/{publication_id}/verify")
def verify_local_publication(pid: str, publication_id: str):
    with get_pool().connection() as conn:
        try:
            record = repository.get_local_publication(conn, pid, publication_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
    return _verify_local_publication(record)


@router.post("/{publication_id}/verify/go")
def verify_local_publication_with_go(pid: str, publication_id: str):
    with get_pool().connection() as conn:
        try:
            record = repository.get_local_publication(conn, pid, publication_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    bundle = _build_package_bundle(record)
    raw_result = _run_go_verifier_for_bundle(bundle)
    summary = _summarize_go_verifier_result(raw_result, record)
    imported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    artifact_id = f"{pid}-go-verifier-provenance-{int(time() * 1000)}"
    artifact_data = {
        "artifact_type": "external_cli_provenance_result",
        "imported_at": imported_at,
        "source_tool": "anip-verify",
        "raw_result": raw_result,
        "summary": summary,
        "local_publication_id": publication_id,
        "reconciled_against_publication_artifact_id": None,
    }
    with get_pool().connection() as conn:
        try:
            artifact = repository.create_pm_artifact(
                conn,
                project_id=pid,
                artifact_id=artifact_id,
                title=f"Verifier Provenance {summary['packageLabel']}",
                data=artifact_data,
            )
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
    return {
        "artifact": artifact,
        "raw_result": raw_result,
        "summary": summary,
    }


@router.post("", status_code=201)
def create_local_publication(pid: str, body: LocalPublicationRequest):
    with get_pool().connection() as conn:
        try:
            validate_publication_saved_revision(conn, pid, body.model_dump())
            built = _build_local_publication(pid, body)
            return repository.create_local_publication(conn, project_id=pid, **built)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except LocalPublicationExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
