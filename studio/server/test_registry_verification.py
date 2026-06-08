"""Tests for Registry-backed verifier provenance."""

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote

from studio.server.routers import registry_verification


def test_registry_go_verifier_persists_external_cli_provenance(client, monkeypatch):
    monkeypatch.setenv("STUDIO_REGISTRY_REQUIRED_MODE", "production")
    monkeypatch.setenv("STUDIO_REGISTRY_TRUSTED_KEY_ID", "registry-prod-2026-04")
    create_project = client.post(
        "/api/projects",
        json={"id": "proj-registry-verification", "name": "Registry Verification Project"},
    )
    assert create_project.status_code == 201, create_project.text
    lineage = {
        "project_ref": "proj-registry-verification",
        "product_revision": {
            "ref": "product-r7",
            "artifact_id": "product-r7",
            "revision_number": 7,
        },
        "developer_revision": {
            "ref": "developer-r9",
            "artifact_id": "developer-r9",
            "revision_number": 9,
            "contract_signature": "sha256:remote-contract",
        },
    }
    publication = client.post(
        "/api/projects/proj-registry-verification/pm-artifacts",
        json={
            "id": "registry-publication-1",
            "title": "Registry Publication",
            "data": {
                "artifact_type": "developer_registry_publication",
                "authority": "remote-registry",
                "publication": {
                    "package_id": "remote-fronting",
                    "package_version": "1.2.3",
                    "published_at": "2026-04-24T00:00:00Z",
                },
                "package": {
                    "package_id": "remote-fronting",
                    "package_version": "1.2.3",
                    "contract_signature": "sha256:remote-contract",
                    "lineage": lineage,
                },
                "receipt": {
                    "registry_signature": "ed25519:remote-receipt",
                    "signature_algorithm": "ed25519",
                    "key_id": "registry-dev-key",
                },
            },
        },
    )
    assert publication.status_code == 201, publication.text

    def fake_run_go_verifier(package_id, package_version, registry_url, required_registry_mode=None, trusted_registry_key_id=None):
        assert package_id == "remote-fronting"
        assert package_version == "1.2.3"
        assert registry_url == "http://registry.test:8200"
        assert required_registry_mode == "production"
        assert trusted_registry_key_id == "registry-prod-2026-04"
        return {
            "status": "ok",
            "package_id": "remote-fronting",
            "package_version": "1.2.3",
            "receipt_status": "verified",
            "registry_receipt_signature": "ed25519:remote-receipt",
            "registry_signing_mode": "production",
            "registry_active_key_id": "registry-prod-2026-04",
            "product_revision": lineage["product_revision"],
            "developer_revision": lineage["developer_revision"],
            "checks": [{"name": "registry_receipt_signature_valid", "status": "pass"}],
        }

    monkeypatch.setattr(registry_verification, "_run_go_verifier_for_registry", fake_run_go_verifier)
    verified = client.post(
        "/api/projects/proj-registry-verification/registry-verification/verify/go",
        json={
            "package_id": "remote-fronting",
            "package_version": "1.2.3",
            "registry_url": "http://registry.test:8200",
            "publication_artifact_id": "registry-publication-1",
        },
    )
    assert verified.status_code == 200, verified.text
    data = verified.json()
    assert data["summary"]["status"] == "aligned"
    assert data["summary"]["matchedPublicationArtifactId"] == "registry-publication-1"
    assert data["summary"]["registrySigningMode"] == "production"
    assert data["summary"]["registryActiveKeyID"] == "registry-prod-2026-04"
    assert data["summary"]["registryTrustPostureLabel"] == "Trusted production Registry"
    assert data["registry_trust_policy"]["required_registry_mode"] == "production"
    assert data["registry_trust_policy"]["trusted_registry_key_id"] == "registry-prod-2026-04"
    assert data["registry_url"] == "http://registry.test:8200"
    assert data["artifact"]["data"]["artifact_type"] == "external_cli_provenance_result"
    assert data["artifact"]["data"]["registry_url"] == "http://registry.test:8200"
    assert data["artifact"]["data"]["summary"]["registrySigningMode"] == "production"
    assert data["artifact"]["data"]["summary"]["registryTrustPostureLabel"] == "Trusted production Registry"

    artifacts = client.get("/api/projects/proj-registry-verification/pm-artifacts")
    assert artifacts.status_code == 200, artifacts.text
    assert any(
        item["data"].get("artifact_type") == "external_cli_provenance_result"
        and item["data"].get("summary", {}).get("status") == "aligned"
        for item in artifacts.json()
    )


def test_registry_go_verifier_uses_real_registry_api_and_go_verifier(client):
    fixture = _build_signed_registry_fixture_with_go()
    server = _start_registry_fixture_server(fixture)
    try:
        registry_url = f"http://127.0.0.1:{server.server_port}"
        create_project = client.post(
            "/api/projects",
            json={"id": "proj-registry-real-go", "name": "Registry Real Go Project"},
        )
        assert create_project.status_code == 201, create_project.text

        publication = client.post(
            "/api/projects/proj-registry-real-go/pm-artifacts",
            json={
                "id": "registry-publication-real-go",
                "title": "Registry Publication Real Go",
                "data": {
                    "artifact_type": "developer_registry_publication",
                    "authority": "remote-registry",
                    "publication": fixture["publication"],
                    "package": fixture["package"],
                    "receipt": fixture["receipt"],
                },
            },
        )
        assert publication.status_code == 201, publication.text

        verified = client.post(
            "/api/projects/proj-registry-real-go/registry-verification/verify/go",
            json={
                "package_id": fixture["package"]["package_id"],
                "package_version": fixture["package"]["package_version"],
                "registry_url": registry_url,
                "publication_artifact_id": "registry-publication-real-go",
            },
        )
        assert verified.status_code == 200, verified.text
        data = verified.json()
        assert data["summary"]["status"] == "aligned"
        assert data["summary"]["receiptStatus"] == "verified"
        assert data["raw_result"]["status"] == "ok"
        assert data["raw_result"]["receipt_status"] == "verified"
        assert data["raw_result"]["registry_signing_mode"] == "dev"
        assert data["raw_result"]["registry_active_key_id"] == fixture["keys"][0]["key_id"]
        assert data["summary"]["registrySigningMode"] == "dev"
        assert data["summary"]["registryActiveKeyID"] == fixture["keys"][0]["key_id"]
        assert data["summary"]["registryTrustPostureLabel"] == "Development Registry"
        assert data["raw_result"]["registry_receipt_signature"] == fixture["receipt"]["registry_signature"]
        assert data["artifact"]["data"]["registry_url"] == registry_url
    finally:
        server.shutdown()
        server.server_close()


def test_registry_summary_marks_trust_policy_failure():
    result = {
        "status": "failed",
        "package_id": "remote-fronting",
        "package_version": "1.2.3",
        "receipt_status": "verified",
        "registry_receipt_signature": "ed25519:remote-receipt",
        "registry_signing_mode": "dev",
        "registry_active_key_id": "anip-registry-dev-ed25519-v1",
        "checks": [
            {"name": "registry_receipt_signature_valid", "status": "pass"},
            {"name": "registry_trust_policy_signing_mode_matches", "status": "fail"},
        ],
    }

    summary = registry_verification._summarize_go_registry_result(
        result,
        "remote-fronting",
        "1.2.3",
        None,
    )

    assert summary["status"] == "mismatch"
    assert summary["registryTrustPostureLabel"] == "Untrusted / policy mismatch"
    assert "registry_trust_policy_signing_mode_matches" in summary["registryTrustPostureDetail"]


def test_registry_verification_uses_stored_trust_policy(client):
    updated = client.put(
        "/api/settings",
        json={
            "registry": {
                "registry_url": "http://127.0.0.1:8300",
                "required_registry_mode": "production",
                "trusted_registry_key_id": "registry-prod-local",
            },
        },
    )
    assert updated.status_code == 200, updated.text

    assert registry_verification._default_registry_url() == "http://127.0.0.1:8300"
    assert registry_verification._default_required_registry_mode() == "production"
    assert registry_verification._trusted_registry_key_id() == "registry-prod-local"


def _build_signed_registry_fixture_with_go():
    source = r'''
package main

import (
	"encoding/json"
	"os"

	"github.com/anip-protocol/anip/packages/go/registryapi"
)

func main() {
	store := registryapi.NewMemoryStore()
	lineage := map[string]any{
		"project_ref": "proj-registry-real-go",
		"product_revision": map[string]any{
			"ref": "product-r8",
			"artifact_id": "product-r8",
			"revision_number": float64(8),
		},
		"developer_revision": map[string]any{
			"ref": "developer-r10",
			"artifact_id": "developer-r10",
			"revision_number": float64(10),
			"contract_signature": "sha256:real-registry-contract",
		},
	}
	result, err := store.PublishPackage(registryapi.PublishPackageRequest{
		PackageID: "remote-fronting-real-go",
		PackageVersion: "2.0.0",
		ProjectRef: "proj-registry-real-go",
		ProductRevisionRef: "product-r8",
		DeveloperRevisionRef: "developer-r10",
		ContractSignature: "sha256:real-registry-contract",
		Lineage: lineage,
		SchemaVersion: "anip-service-definition/v1",
		Manifest: map[string]any{
			"anip_spec_version": "anip/0.24",
			"name": "Remote Fronting Real",
			"version": "2.0.0",
			"agent_consumption_readiness": map[string]any{
				"artifact_type": "agent_consumption_readiness",
				"status": "ready",
				"score": float64(100),
				"summary": map[string]any{
					"blockers": float64(0),
					"warnings": float64(0),
					"info": float64(0),
					"probes": float64(1),
					"required_app_glue": float64(0),
				},
				"findings": []any{},
				"probes": []any{map[string]any{"id": "probe-1", "expected_outcome": "success"}},
				"required_app_glue": []any{},
			},
			"agent_consumability": map[string]any{
				"artifact_type": "agent_consumability_metadata",
				"schema_version": "anip-agent-consumability/v0",
				"capabilities": map[string]any{
					"remote.search": map[string]any{
						"intent": map[string]any{
							"category": "remote.search",
							"summary": "Search remote records.",
						},
						"business_effects": map[string]any{
							"produces": []any{"data.read"},
							"does_not_produce": []any{"system.mutation"},
						},
					},
				},
			},
		},
		ServiceDefinition: map[string]any{
			"artifact_type": "anip_service_definition",
			"contract_schema_version": "anip-service-definition/v1",
			"identity": map[string]any{
				"system_name": "Remote Fronting Real",
				"domain_name": "test",
				"delivery_model": "standalone_service",
				"architecture_shape": "single_service",
			},
			"compiled_contract_identity": map[string]any{
				"signature": "sha256:real-registry-contract",
				"signature_algorithm": "sha256",
			},
			"service_topology_bindings": []any{
				map[string]any{
					"id": "svc-remote-fronting",
					"service_id": "remote-fronting",
					"service_name": "Remote Fronting",
					"source_role": "data_access",
					"source_capabilities": []any{"remote.search"},
					"formalized_capability_ids": []any{"remote.search"},
				},
			},
			"capability_formalizations": []any{
				map[string]any{
					"id": "cap-remote-search",
					"source_kind": "data_access",
					"service_id": "remote-fronting",
					"capability_id": "remote.search",
					"kind": "atomic",
					"title": "Search Remote Records",
					"summary": "Search remote records.",
					"intent_type": "read_only",
					"operation_type": "query",
					"side_effect_level": "none",
					"backend_operation": "searchRemoteRecords",
					"path_template": "/remote/search",
					"output_shape": "remote_search_result",
					"inputs": []any{
						map[string]any{
							"input_name": "query",
							"input_type": "string",
							"required": true,
							"summary": "Search query.",
						},
					},
				},
			},
		},
		RecommendedLock: map[string]any{"verifier_pack": map[string]any{"name": "anip-verifier"}},
	})
	if err != nil {
		panic(err)
	}
	_ = json.NewEncoder(os.Stdout).Encode(map[string]any{
		"publication": result.Publication,
		"package": result.Package,
		"receipt": result.Receipt,
		"keys": store.ListPublicKeys(),
	})
}
'''
    with TemporaryDirectory(dir=registry_verification.GO_PACKAGES_DIR) as temp_dir:
        main_path = Path(temp_dir) / "main.go"
        main_path.write_text(source, encoding="utf-8")
        result = subprocess.run(
            ["go", "run", str(main_path)],
            cwd=str(registry_verification.GO_PACKAGES_DIR),
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    return json.loads(result.stdout)


def _start_registry_fixture_server(fixture):
    package_record = fixture["package"]
    receipt = fixture["receipt"]
    keys = fixture["keys"]
    package_path = f"/registry-api/v1/packages/{package_record['package_id']}/{package_record['package_version']}"
    package_download_path = f"{package_path}/download"
    receipt_path = f"{package_path}/receipt"

    class RegistryFixtureHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = unquote(self.path)
            if path == "/registry-api/v1/healthz":
                self._write_json({
                    "status": "ok",
                    "service": "anip-registry-fixture",
                    "signing_mode": "dev",
                    "active_key_id": keys[0]["key_id"],
                })
                return
            if path == package_path:
                self._write_json(package_record)
                return
            if path == package_download_path:
                self._write_json(package_record)
                return
            if path == receipt_path:
                self._write_json(receipt)
                return
            if path == "/registry-api/v1/keys":
                self._write_json({
                    "signing_mode": "dev",
                    "active_key_id": keys[0]["key_id"],
                    "items": keys,
                })
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, *_args):
            return

        def _write_json(self, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), RegistryFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
