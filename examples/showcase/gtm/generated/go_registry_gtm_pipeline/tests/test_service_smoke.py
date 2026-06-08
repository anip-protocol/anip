import pytest
from fastapi.testclient import TestClient

from gtm_pipeline_q2_review.app import create_app
from gtm_pipeline_q2_review.runtime_target import GENERATED_CAPABILITY_METADATA

@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())

def _issue_token(client: TestClient, capability_id: str, scope: list[str]) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": "Bearer dev-admin-key"},
        json={"capability": capability_id, "scope": scope},
    )
    assert response.status_code == 200
    return response.json()["token"]

def test_generated_service_discovery_and_invoke(client: TestClient) -> None:
    discovery = client.get('/.well-known/anip')
    assert discovery.status_code == 200

    capability = GENERATED_CAPABILITY_METADATA[0]
    token = _issue_token(client, capability['capability_id'], capability['minimum_scope'])
    invoke = client.post(
        f"/anip/invoke/{capability['capability_id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": capability["sample_parameters"]},
    )
    assert invoke.status_code == 200
    payload = invoke.json()
    assert payload["success"] is True
    assert payload["result"]["execution_status"]
