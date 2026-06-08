"""Tests for the validation API server."""
import sys
from pathlib import Path

# Ensure we can import the server module
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from server.app import app

client = TestClient(app)


def make_travel_pack():
    """Return a compact valid pack for validate-endpoint smoke coverage."""
    return {
        "requirements": {
            "system": {
                "name": "Travel Booking",
                "domain": "travel",
                "deployment_intent": "production",
            },
            "transports": {"http": True, "stdio": False, "grpc": False},
            "trust": {"mode": "signed", "checkpoints": True},
            "auth": {
                "delegation_tokens": True,
                "purpose_binding": True,
                "scoped_authority": True,
                "service_to_service_handoffs": False,
            },
            "permissions": {
                "preflight_discovery": True,
                "restricted_vs_denied": True,
                "grantable_requirements": False,
            },
            "audit": {
                "durable": True,
                "searchable": True,
                "cross_service_reconstruction_required": False,
            },
            "lineage": {
                "invocation_id": True,
                "client_reference_id": True,
                "task_id": True,
                "parent_invocation_id": False,
                "cross_service_continuity_required": False,
            },
            "scale": {
                "shape_preference": "production_single_service",
                "high_availability": True,
            },
        },
        "proposal": {
            "proposal": {
                "recommended_shape": "production_single_service",
                "rationale": ["Single bounded booking service is enough for this workflow."],
                "required_components": ["anip service", "audit trail"],
                "declared_surfaces": {
                    "authority_posture": True,
                    "budget_enforcement": True,
                },
            }
        },
        "scenario": {
            "scenario": {
                "name": "travel_booking_with_budget_check",
                "category": "safety",
                "narrative": "An employee books travel and the service must enforce budget and approval rules.",
                "context": {"budget_limit": 1000, "approval_required": True},
                "expected_behavior": [
                    "budget is checked before booking",
                    "approval posture is explicit",
                ],
                "expected_anip_support": ["delegation tokens", "durable audit"],
            }
        },
    }

def test_health_returns_ok():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_readyz_returns_migration_status(client):
    resp = client.get("/api/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "anip-studio"
    assert body["migration"]["applied"] is True
    assert body["migration"]["expected_count"] > 0

def test_metrics_returns_prometheus_text(client):
    client.get("/api/health")
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    assert "anip_studio_http_requests_total" in resp.text
    assert "anip_studio_migrations_applied" in resp.text

def test_validate_travel_single():
    pack = make_travel_pack()
    resp = client.post("/api/validate", json=pack)
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation"]["result"] in ("HANDLED", "PARTIAL", "REQUIRES_GLUE")

def test_validate_response_has_required_fields():
    pack = make_travel_pack()
    resp = client.post("/api/validate", json=pack)
    ev = resp.json()["evaluation"]
    for field in ["scenario_name", "result", "handled_by_anip", "glue_you_will_still_write", "glue_category", "why", "what_would_improve"]:
        assert field in ev, f"Missing field: {field}"

def test_validate_invalid_input():
    resp = client.post("/api/validate", json={"requirements": {}, "proposal": {}, "scenario": {}})
    assert resp.status_code == 422
