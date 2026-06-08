"""Tests for Studio-local immutable publication records."""

from copy import deepcopy

from studio.server.routers import local_publications
from studio.server.routers.local_publications import _verify_local_publication


def valid_anip_service_definition(signature: str) -> dict:
    return {
        "artifact_type": "anip_service_definition",
        "contract_schema_version": "anip-service-definition/v1",
        "compiled_contract_identity": {
            "signature": signature,
            "signature_algorithm": "sha256",
        },
        "identity": {
            "system_name": "Work Item Fronting & Routing",
            "domain_name": "work_items",
            "delivery_model": "standalone_service",
            "architecture_shape": "single_service",
        },
        "service_topology_bindings": [
            {
                "id": "svc-work-items",
                "service_id": "work-items",
                "service_name": "Work Items",
                "source_role": "data_access",
                "source_capabilities": ["work_item.search"],
                "formalized_capability_ids": ["work_item.search"],
                "owned_concept_ids": ["work_item"],
            }
        ],
        "capability_formalizations": [
            {
                "id": "cap-work-item-search",
                "source_kind": "data_access",
                "service_id": "work-items",
                "capability_id": "work_item.search",
                "kind": "atomic",
                "title": "Search Work Items",
                "summary": "Search & summarize governed work items.",
                "intent_type": "read_only",
                "operation_type": "query",
                "side_effect_level": "none",
                "backend_operation": "searchWorkItems",
                "path_template": "/work-items/search",
                "output_shape": "work_item_search_result",
                "inputs": [
                    {
                        "input_name": "query",
                        "input_type": "string",
                        "required": True,
                        "summary": "Search query.",
                    }
                ],
            }
        ],
    }


def create_saved_developer_definition_for_publication(client, project_id: str, payload: dict) -> None:
    lineage = payload.get("lineage") or {}
    developer_lineage = lineage.get("developer_revision") or {}
    product_lineage = lineage.get("product_revision") or {}
    revision_ref = payload["developer_revision_ref"]
    revision_number = developer_lineage.get("revision_number")
    signature = payload["contract_signature"]
    source_inputs = {
        "product_revision_artifact_id": product_lineage.get("artifact_id"),
        "product_revision_number": product_lineage.get("revision_number"),
    }
    saved_revision = {
        "revision_number": revision_number,
        "revision_artifact_id": revision_ref,
        "previous_revision_artifact_id": None,
        "saved_at": "2026-05-10T00:00:00Z",
    }
    current_payload = {
        "artifact_type": "developer_definition",
        "compiled_contract_identity": {"signature": signature},
        "saved_revision": saved_revision,
        "source_inputs": source_inputs,
    }
    revision_payload = {
        **current_payload,
        "artifact_type": "developer_definition_revision",
    }
    created_revision = client.post(
        f"/api/projects/{project_id}/pm-artifacts",
        json={
            "id": revision_ref,
            "title": f"Developer Definition Revision {revision_number or revision_ref}",
            "data": revision_payload,
        },
    )
    assert created_revision.status_code == 201, created_revision.text
    created_current = client.post(
        f"/api/projects/{project_id}/pm-artifacts",
        json={
            "id": f"{project_id}-developer-definition",
            "title": "Developer Definition",
            "data": current_payload,
        },
    )
    assert created_current.status_code == 201, created_current.text
    activated = client.put(
        f"/api/projects/{project_id}/pm-artifacts/{project_id}-developer-definition",
        json={"status": "active"},
    )
    assert activated.status_code == 200, activated.text


def test_create_and_list_local_publication(client):
    create_project = client.post(
        "/api/projects",
        json={"id": "proj-local-publication", "name": "Local Publication Project"},
    )
    assert create_project.status_code == 201, create_project.text

    payload = {
        "package_id": "work-item-fronting",
        "package_version": "0.1.1",
        "project_ref": "proj-local-publication",
        "product_revision_ref": "baseline:2026-04-24T00:00:00Z",
        "developer_revision_ref": "developer-definition-revision-1",
        "contract_signature": "sha256:contract",
        "schema_version": "anip-service-definition/v1",
        "lineage": {
            "project_ref": "proj-local-publication",
            "product_revision": {
                "ref": "baseline:2026-04-24T00:00:00Z",
                "artifact_id": "product-revision-2",
                "revision_number": 2,
                "baseline_locked_at": "2026-04-24T00:00:00Z",
            },
            "developer_revision": {
                "ref": "developer-definition-revision-1",
                "artifact_id": "developer-definition-revision-1",
                "revision_number": 1,
                "contract_signature": "sha256:contract",
            },
        },
        "manifest": {
            "name": "Work Item Fronting",
            "version": "0.1.1",
            "anip_spec_version": "anip/0.24",
            "readme": "Work Item Fronting local package.",
            "source_links": [
                {
                    "title": "Studio Project",
                    "url": "http://localhost:5173/studio/design/projects/proj-local-publication",
                }
            ],
        },
        "implementation_materials": [
            {
                "title": "Reviewed app glue",
                "ref": "registry://acme/work-item-glue@1.2.3#sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                "bundle_tree_sha256": "sha256:abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd",
            }
        ],
        "service_definition": {
            "artifact_type": "developer_definition",
            "compiled_contract_identity": {"signature": "sha256:contract"},
        },
        "recommended_lock": {"verifier_pack": {"name": "anip-verifier"}},
    }
    create_saved_developer_definition_for_publication(client, "proj-local-publication", payload)
    resp = client.post(
        "/api/projects/proj-local-publication/local-publications",
        json=payload,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["authority"] == "local-studio"
    assert data["publication"]["package_id"] == "work-item-fronting"
    assert data["publication"]["lineage"]["product_revision"]["revision_number"] == 2
    assert data["package"]["lineage"]["developer_revision"]["revision_number"] == 1
    assert data["package"]["readme"] == "Work Item Fronting local package."
    assert data["package"]["source_links"][0]["title"] == "Studio Project"
    assert data["package"]["implementation_materials"][0]["title"] == "Reviewed app glue"
    assert (
        data["package"]["manifest"]["implementation_material"]["custom_code_bundles"][0]["ref"]
        == payload["implementation_materials"][0]["ref"]
    )
    assert data["package"]["definition_digest"].startswith("sha256:")
    assert data["receipt"]["registry_signature"].startswith("sha256:")
    assert data["receipt"]["authority"] == "local-studio"

    listed = client.get("/api/projects/proj-local-publication/local-publications")
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"][0]["package"]["package_version"] == "0.1.1"

    bundle = client.get(
        f"/api/projects/proj-local-publication/local-publications/{data['id']}/bundle"
    )
    assert bundle.status_code == 200, bundle.text
    assert bundle.headers["content-disposition"].endswith(".anip-package.json\"")
    bundle_data = bundle.json()
    assert bundle_data["bundle_schema_version"] == "anip-package-bundle/v1"
    assert bundle_data["authority"] == "local-studio"
    assert bundle_data["package"]["package_id"] == "work-item-fronting"
    assert bundle_data["lineage"]["product_revision"]["artifact_id"] == "product-revision-2"
    assert bundle_data["package"]["lineage"] == payload["lineage"]
    assert bundle_data["package"]["implementation_materials"][0]["ref"] == payload["implementation_materials"][0]["ref"]
    assert (
        bundle_data["manifest"]["implementation_material"]["custom_code_bundles"][0]["bundle_tree_sha256"]
        == payload["implementation_materials"][0]["bundle_tree_sha256"]
    )
    expected_manifest = deepcopy(payload["manifest"])
    expected_manifest["implementation_material"] = {
        "custom_code_bundles": payload["implementation_materials"],
    }
    assert bundle_data["receipt"]["registry_signature"] == data["receipt"]["registry_signature"]
    assert bundle_data["manifest"] == expected_manifest
    assert bundle_data["service_definition"] == payload["service_definition"]
    expected_lock = deepcopy(payload["recommended_lock"])
    expected_lock["anip_spec_version"] = "anip/0.24"
    assert bundle_data["lock"] == expected_lock
    assert bundle_data["digests"]["service_definition"] == data["package"]["definition_digest"]

    verification = client.post(
        f"/api/projects/proj-local-publication/local-publications/{data['id']}/verify"
    )
    assert verification.status_code == 200, verification.text
    verification_data = verification.json()
    assert verification_data["status"] == "ok"
    assert verification_data["receipt_status"] == "verified"
    assert verification_data["package_id"] == "work-item-fronting"
    assert verification_data["product_revision"]["revision_number"] == 2
    assert verification_data["developer_revision"]["revision_number"] == 1
    assert {check["status"] for check in verification_data["checks"]} == {"pass"}


def test_create_local_publication_accepts_studio_project_ref(client):
    create_project = client.post(
        "/api/projects",
        json={"id": "proj-local-publication-studio-ref", "name": "Studio Ref Publication Project"},
    )
    assert create_project.status_code == 201, create_project.text

    payload = {
        "package_id": "work-item-fronting",
        "package_version": "0.1.2",
        "project_ref": "studio:proj-local-publication-studio-ref",
        "product_revision_ref": "product-revision-1@r1",
        "developer_revision_ref": "developer-definition-revision-studio-ref-1",
        "contract_signature": "sha256:contract",
        "schema_version": "anip-service-definition/v1",
        "lineage": {
            "project_ref": "studio:proj-local-publication-studio-ref",
            "product_revision": {
                "ref": "product-revision-1@r1",
                "artifact_id": "product-revision-1",
                "revision_number": 1,
                "baseline_locked_at": "2026-05-10T00:00:00Z",
            },
            "developer_revision": {
                "ref": "developer-definition-revision-studio-ref-1",
                "artifact_id": "developer-definition-revision-studio-ref-1",
                "revision_number": 1,
                "contract_signature": "sha256:contract",
            },
        },
        "manifest": {
            "name": "Work Item Fronting",
            "version": "0.1.2",
            "anip_spec_version": "anip/0.24",
            "readme": "Work Item Fronting local package.",
        },
        "service_definition": valid_anip_service_definition("sha256:contract"),
        "recommended_lock": {"verifier_pack": {"name": "anip-verifier"}},
    }
    create_saved_developer_definition_for_publication(client, "proj-local-publication-studio-ref", payload)

    resp = client.post(
        "/api/projects/proj-local-publication-studio-ref/local-publications",
        json=payload,
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["publication"]["project_ref"] == "studio:proj-local-publication-studio-ref"


def test_local_publication_package_version_is_immutable(client):
    create_project = client.post(
        "/api/projects",
        json={"id": "proj-local-publication-conflict", "name": "Local Publication Conflict"},
    )
    assert create_project.status_code == 201, create_project.text
    payload = {
        "package_id": "work-item-fronting",
        "package_version": "0.1.1",
        "project_ref": "proj-local-publication-conflict",
        "product_revision_ref": "baseline:locked",
        "developer_revision_ref": "developer-r1",
        "contract_signature": "sha256:contract",
        "manifest": {"name": "Work Item Fronting", "anip_spec_version": "anip/0.24"},
        "service_definition": {"artifact_type": "developer_definition"},
        "recommended_lock": {},
    }
    payload["service_definition"] = {
        "artifact_type": "developer_definition",
        "compiled_contract_identity": {"signature": payload["contract_signature"]},
    }
    create_saved_developer_definition_for_publication(client, "proj-local-publication-conflict", payload)
    first = client.post(
        "/api/projects/proj-local-publication-conflict/local-publications",
        json=payload,
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/projects/proj-local-publication-conflict/local-publications",
        json={**payload, "manifest": {**payload["manifest"], "name": "Changed package metadata"}},
    )
    assert second.status_code == 409, second.text


def test_local_publication_rejects_transient_contract_not_matching_saved_revision(client):
    create_project = client.post(
        "/api/projects",
        json={"id": "proj-local-publication-transient", "name": "Local Publication Transient"},
    )
    assert create_project.status_code == 201, create_project.text
    payload = {
        "package_id": "work-item-fronting",
        "package_version": "0.1.2",
        "project_ref": "proj-local-publication-transient",
        "product_revision_ref": "baseline:locked",
        "developer_revision_ref": "developer-r1-transient",
        "contract_signature": "sha256:saved-contract",
        "manifest": {"name": "Work Item Fronting", "anip_spec_version": "anip/0.24"},
        "service_definition": {
            "artifact_type": "developer_definition",
            "compiled_contract_identity": {"signature": "sha256:saved-contract"},
        },
        "recommended_lock": {},
    }
    create_saved_developer_definition_for_publication(client, "proj-local-publication-transient", payload)

    transient_payload = deepcopy(payload)
    transient_payload["service_definition"]["compiled_contract_identity"]["signature"] = "sha256:unsaved-draft"
    created = client.post(
        "/api/projects/proj-local-publication-transient/local-publications",
        json=transient_payload,
    )
    assert created.status_code == 422, created.text
    assert "service_definition compiled contract signature must match contract_signature" in created.text


def test_local_publication_rejects_non_current_anip_spec(client):
    create_project = client.post(
        "/api/projects",
        json={"id": "proj-local-publication-old-spec", "name": "Local Publication Old Spec"},
    )
    assert create_project.status_code == 201, create_project.text
    payload = {
        "package_id": "work-item-fronting",
        "package_version": "0.2.0",
        "project_ref": "proj-local-publication-old-spec",
        "product_revision_ref": "baseline:locked",
        "developer_revision_ref": "developer-r2-tamper",
        "contract_signature": "sha256:contract",
        "schema_version": "anip-service-definition/v1",
        "manifest": {"name": "Work Item Fronting", "anip_spec_version": "anip/0.23"},
        "service_definition": {"artifact_type": "developer_definition"},
        "recommended_lock": {},
    }
    payload["service_definition"] = {
        "artifact_type": "developer_definition",
        "compiled_contract_identity": {"signature": payload["contract_signature"]},
    }
    create_saved_developer_definition_for_publication(client, "proj-local-publication-old-spec", payload)
    created = client.post(
        "/api/projects/proj-local-publication-old-spec/local-publications",
        json=payload,
    )
    assert created.status_code == 422, created.text
    assert "anip_spec_version must be anip/0.24" in created.text


def test_local_publication_verification_fails_for_tampered_record(client):
    create_project = client.post(
        "/api/projects",
        json={"id": "proj-local-publication-tamper", "name": "Local Publication Tamper"},
    )
    assert create_project.status_code == 201, create_project.text
    payload = {
        "package_id": "work-item-fronting",
        "package_version": "0.2.0",
        "project_ref": "proj-local-publication-tamper",
        "product_revision_ref": "baseline:locked",
        "developer_revision_ref": "developer-r2",
        "contract_signature": "sha256:contract",
        "manifest": {"name": "Work Item Fronting", "version": "0.2.0", "anip_spec_version": "anip/0.24"},
        "service_definition": {
            "artifact_type": "developer_definition",
            "compiled_contract_identity": {"signature": "sha256:contract"},
        },
        "recommended_lock": {},
    }
    create_saved_developer_definition_for_publication(client, "proj-local-publication-tamper", payload)
    created = client.post(
        "/api/projects/proj-local-publication-tamper/local-publications",
        json=payload,
    )
    assert created.status_code == 201, created.text

    tampered = deepcopy(created.json())
    tampered["package"]["manifest"]["version"] = "0.2.1"
    result = _verify_local_publication(tampered)

    assert result["status"] == "failed"
    assert result["receipt_status"] == "failed"
    failed_checks = {check["name"] for check in result["checks"] if check["status"] == "fail"}
    assert "manifest_digest_matches" in failed_checks
    assert "receipt_signature_matches" in failed_checks


def test_go_verifier_endpoint_persists_external_cli_provenance(client, monkeypatch):
    create_project = client.post(
        "/api/projects",
        json={"id": "proj-local-publication-go", "name": "Local Publication Go"},
    )
    assert create_project.status_code == 201, create_project.text
    payload = {
        "package_id": "work-item-fronting",
        "package_version": "0.3.0",
        "project_ref": "proj-local-publication-go",
        "product_revision_ref": "product-r2",
        "developer_revision_ref": "developer-r3",
        "contract_signature": "sha256:contract",
        "lineage": {
            "project_ref": "proj-local-publication-go",
            "product_revision": {
                "ref": "product-r2",
                "artifact_id": "product-r2",
                "revision_number": 2,
            },
            "developer_revision": {
                "ref": "developer-r3",
                "artifact_id": "developer-r3",
                "revision_number": 3,
                "contract_signature": "sha256:contract",
            },
        },
        "manifest": {"name": "Work Item Fronting", "version": "0.3.0", "anip_spec_version": "anip/0.24"},
        "service_definition": {
            "artifact_type": "developer_definition",
            "compiled_contract_identity": {"signature": "sha256:contract"},
        },
        "recommended_lock": {},
    }
    create_saved_developer_definition_for_publication(client, "proj-local-publication-go", payload)
    created = client.post(
        "/api/projects/proj-local-publication-go/local-publications",
        json=payload,
    )
    assert created.status_code == 201, created.text
    publication = created.json()

    def fake_run_go_verifier(bundle):
        assert bundle["package"]["package_id"] == "work-item-fronting"
        return {
            "status": "ok",
            "package_id": "work-item-fronting",
            "package_version": "0.3.0",
            "receipt_status": "verified",
            "registry_receipt_signature": publication["receipt"]["registry_signature"],
            "product_revision": payload["lineage"]["product_revision"],
            "developer_revision": payload["lineage"]["developer_revision"],
            "checks": [{"name": "bundle_receipt_signature_matches", "status": "pass"}],
        }

    monkeypatch.setattr(local_publications, "_run_go_verifier_for_bundle", fake_run_go_verifier)
    verified = client.post(
        f"/api/projects/proj-local-publication-go/local-publications/{publication['id']}/verify/go"
    )
    assert verified.status_code == 200, verified.text
    data = verified.json()
    assert data["summary"]["status"] == "aligned", data
    assert data["summary"]["sourceTool"] == "anip-verify"
    assert data["artifact"]["data"]["artifact_type"] == "external_cli_provenance_result"
    assert data["artifact"]["data"]["raw_result"]["receipt_status"] == "verified"

    artifacts = client.get("/api/projects/proj-local-publication-go/pm-artifacts")
    assert artifacts.status_code == 200, artifacts.text
    assert any(
        item["data"].get("artifact_type") == "external_cli_provenance_result"
        for item in artifacts.json()
    )


def test_go_verifier_endpoint_uses_real_go_verifier(client):
    create_project = client.post(
        "/api/projects",
        json={"id": "proj-local-publication-real-go", "name": "Local Publication Real Go"},
    )
    assert create_project.status_code == 201, create_project.text
    payload = {
        "package_id": "work-item-fronting-real-go",
        "package_version": "0.4.0",
        "project_ref": "proj-local-publication-real-go",
        "product_revision_ref": "product-r4",
        "developer_revision_ref": "developer-r6",
        "contract_signature": "sha256:real-go-contract",
        "lineage": {
            "project_ref": "proj-local-publication-real-go",
            "product_revision": {
                "ref": "product-r4",
                "artifact_id": "product-r4",
                "revision_number": 4,
            },
            "developer_revision": {
                "ref": "developer-r6",
                "artifact_id": "developer-r6",
                "revision_number": 6,
                "contract_signature": "sha256:real-go-contract",
            },
        },
        "manifest": {
            "name": "Work Item Fronting Real Go",
            "version": "0.4.0",
            "anip_spec_version": "anip/0.24",
            "agent_consumption_readiness": {
                "artifact_type": "agent_consumption_readiness",
                "status": "ready",
                "score": 100,
                "summary": {"blockers": 0, "warnings": 0, "info": 0, "probes": 1, "required_app_glue": 0},
                "findings": [],
                "probes": [{"id": "probe-1", "label": "Probe", "prompt": "Search work items", "expected_outcome": "success", "rationale": "Smoke"}],
                "required_app_glue": [],
            },
            "agent_consumability": {
                "artifact_type": "agent_consumability_metadata",
                "schema_version": "anip-agent-consumability/v0",
                "capabilities": {"work_item.search": {"intent": {"category": "work_item.search", "summary": "Search work items"}}},
            },
        },
        "service_definition": valid_anip_service_definition("sha256:real-go-contract"),
        "recommended_lock": {"verifier_pack": {"name": "anip-verifier"}},
    }
    create_saved_developer_definition_for_publication(client, "proj-local-publication-real-go", payload)
    created = client.post(
        "/api/projects/proj-local-publication-real-go/local-publications",
        json=payload,
    )
    assert created.status_code == 201, created.text
    publication = created.json()

    verified = client.post(
        f"/api/projects/proj-local-publication-real-go/local-publications/{publication['id']}/verify/go"
    )
    assert verified.status_code == 200, verified.text
    data = verified.json()
    assert data["summary"]["status"] == "aligned", data
    assert data["summary"]["receiptStatus"] == "verified"
    assert data["raw_result"]["status"] == "ok"
    assert data["raw_result"]["receipt_status"] == "verified"
    assert data["raw_result"]["product_revision"]["artifact_id"] == "product-r4"
    assert data["raw_result"]["developer_revision"]["artifact_id"] == "developer-r6"
    assert data["artifact"]["data"]["raw_result"]["registry_receipt_signature"] == publication["receipt"]["registry_signature"]
