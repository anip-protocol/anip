"""Conformance tests for ANIP checkpoint and proof behavior.

Spec references: §6.5 (checkpoints).

Checkpoint endpoints are only required for services with trust_level
'anchored' or 'attested'. Tests are skipped if the service does not
advertise checkpoint support in its discovery document.
"""
import pytest


def _has_checkpoints(discovery: dict) -> bool:
    """Check if the service advertises checkpoint support."""
    return "checkpoints" in discovery.get("endpoints", {})


class TestCheckpoints:
    def test_list_checkpoints_returns_200(self, client, discovery):
        if not _has_checkpoints(discovery):
            pytest.skip("Service does not advertise checkpoint endpoint")
        resp = client.get("/anip/checkpoints")
        assert resp.status_code == 200

    def test_list_checkpoints_shape(self, client, discovery):
        if not _has_checkpoints(discovery):
            pytest.skip("Service does not advertise checkpoint endpoint")
        resp = client.get("/anip/checkpoints")
        data = resp.json()
        assert "checkpoints" in data
        assert isinstance(data["checkpoints"], list)

    def test_checkpoint_entry_fields(self, client, discovery):
        if not _has_checkpoints(discovery):
            pytest.skip("Service does not advertise checkpoint endpoint")
        resp = client.get("/anip/checkpoints")
        data = resp.json()
        if len(data["checkpoints"]) > 0:
            cp = data["checkpoints"][0]
            assert "checkpoint_id" in cp
            assert "merkle_root" in cp
            assert "timestamp" in cp

    def test_checkpoint_not_found(self, client, discovery):
        if not _has_checkpoints(discovery):
            pytest.skip("Service does not advertise checkpoint endpoint")
        resp = client.get("/anip/checkpoints/nonexistent_cp_id_xyz")
        assert resp.status_code == 404

    def test_checkpoint_proof_request(self, client, discovery):
        """If checkpoints exist, test proof request behavior."""
        if not _has_checkpoints(discovery):
            pytest.skip("Service does not advertise checkpoint endpoint")
        resp = client.get("/anip/checkpoints")
        data = resp.json()
        if len(data["checkpoints"]) == 0:
            pytest.skip("No checkpoints available to test proof behavior")

        cp_id = data["checkpoints"][0]["checkpoint_id"]
        resp = client.get(f"/anip/checkpoints/{cp_id}?include_proof=true&leaf_index=0")
        assert resp.status_code == 200
        detail = resp.json()
        # Should have either inclusion_proof or proof_unavailable
        has_proof = "inclusion_proof" in detail
        has_unavailable = "proof_unavailable" in detail
        assert has_proof or has_unavailable, (
            "Checkpoint detail with include_proof=true should have "
            "'inclusion_proof' or 'proof_unavailable'"
        )
