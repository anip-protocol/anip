"""Tests for the validation API server."""
import sys
from pathlib import Path
import yaml

# Ensure we can import the server module
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from server.app import app

client = TestClient(app)

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "tooling" / "examples"

def load_pack(name):
    """Load a pack's YAML files as dicts."""
    pack_dir = EXAMPLES_DIR / name
    result = {}
    for fname in ["requirements", "proposal", "scenario"]:
        p = pack_dir / f"{fname}.yaml"
        if p.exists():
            with open(p) as f:
                result[fname] = yaml.safe_load(f)
    return result

def test_health_returns_ok():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_validate_travel_single():
    pack = load_pack("travel-single")
    resp = client.post("/api/validate", json=pack)
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation"]["result"] in ("HANDLED", "PARTIAL", "REQUIRES_GLUE")

def test_validate_response_has_required_fields():
    pack = load_pack("travel-single")
    resp = client.post("/api/validate", json=pack)
    ev = resp.json()["evaluation"]
    for field in ["scenario_name", "result", "handled_by_anip", "glue_you_will_still_write", "glue_category", "why", "what_would_improve"]:
        assert field in ev, f"Missing field: {field}"

def test_validate_invalid_input():
    resp = client.post("/api/validate", json={"requirements": {}, "proposal": {}, "scenario": {}})
    assert resp.status_code == 422
