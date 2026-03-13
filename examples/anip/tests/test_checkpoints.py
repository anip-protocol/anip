"""Tests for checkpoint creation and storage."""
import json
import pytest

AUTH = {"Authorization": "Bearer demo-human-key"}


def _issue_token(client, capability, scope):
    resp = client.post("/anip/tokens", json={
        "subject": "agent:test",
        "scope": scope,
        "capability": capability,
    }, headers=AUTH)
    return resp.json()["token"]


class TestCheckpointCreation:
    def test_create_checkpoint_returns_body_and_detached_signature(self, client):
        token = _issue_token(client, "search_flights", ["travel.search"])
        for _ in range(3):
            client.post("/anip/invoke/search_flights",
                        json={"token": token, "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-04-01"}})
        from anip_server.data.database import get_merkle_snapshot, create_checkpoint
        snap = get_merkle_snapshot()
        body, signature = create_checkpoint()
        assert body["merkle_root"] == snap["root"]
        assert body["range"]["last_sequence"] == snap["leaf_count"]
        assert "timestamp" in body
        assert "signature" not in body
        assert signature.count(".") == 2
        assert signature.split(".")[1] == ""

    def test_checkpoint_stored_in_database(self, client):
        token = _issue_token(client, "search_flights", ["travel.search"])
        client.post("/anip/invoke/search_flights",
                    json={"token": token, "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-04-01"}})
        from anip_server.data.database import create_checkpoint, get_checkpoints
        create_checkpoint()
        checkpoints = get_checkpoints()
        assert len(checkpoints) >= 1
        assert checkpoints[-1]["merkle_root"].startswith("sha256:")

    def test_checkpoint_chains_to_previous(self, client):
        token = _issue_token(client, "search_flights", ["travel.search"])
        from anip_server.data.database import create_checkpoint, get_checkpoints
        for _ in range(2):
            client.post("/anip/invoke/search_flights",
                        json={"token": token, "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-04-01"}})
            create_checkpoint()
        checkpoints = get_checkpoints()
        assert checkpoints[0]["previous_checkpoint"] is None
        assert checkpoints[1]["previous_checkpoint"] is not None


class TestCheckpointPolicy:
    def test_cadence_policy_triggers(self):
        from anip_server.primitives.checkpoint import CheckpointPolicy
        policy = CheckpointPolicy(entry_count=5)
        for i in range(4):
            assert not policy.should_checkpoint(entries_since_last=i + 1)
        assert policy.should_checkpoint(entries_since_last=5)

    def test_no_policy_never_triggers(self):
        from anip_server.primitives.checkpoint import CheckpointPolicy
        policy = CheckpointPolicy()
        assert not policy.should_checkpoint(entries_since_last=1000)
