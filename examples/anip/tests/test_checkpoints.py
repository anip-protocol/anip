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


class TestAutoCheckpoint:
    def test_auto_checkpoint_after_n_entries(self, client):
        """With entry_count policy=3, a checkpoint should be created after every 3 entries."""
        from anip_server.data.database import set_checkpoint_policy, get_checkpoints
        from anip_server.primitives.checkpoint import CheckpointPolicy
        set_checkpoint_policy(CheckpointPolicy(entry_count=3))
        token = _issue_token(client, "search_flights", ["travel.search"])
        for _ in range(3):
            client.post(
                "/anip/invoke/search_flights",
                json={"token": token, "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-04-01"}},
            )
        checkpoints = get_checkpoints()
        assert len(checkpoints) >= 1
        # Clean up policy
        set_checkpoint_policy(None)

    def test_time_based_checkpoint(self, client):
        """CheckpointScheduler fires independently — no subsequent write needed."""
        import time
        from anip_server.data.database import (
            set_checkpoint_policy,
            get_checkpoints,
            has_new_entries_since_checkpoint,
            create_checkpoint,
        )
        from anip_server.primitives.checkpoint import CheckpointPolicy, CheckpointScheduler
        set_checkpoint_policy(CheckpointPolicy(interval_seconds=1))
        token = _issue_token(client, "search_flights", ["travel.search"])
        client.post(
            "/anip/invoke/search_flights",
            json={"token": token, "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-04-01"}},
        )
        initial_checkpoints = get_checkpoints(limit=100)
        initial_count = len(initial_checkpoints)
        # Start scheduler
        scheduler = CheckpointScheduler(1, create_checkpoint, has_new_entries_since_checkpoint)
        scheduler.start()
        time.sleep(1.5)
        scheduler.stop()
        checkpoints = get_checkpoints(limit=100)
        assert len(checkpoints) > initial_count, (
            "CheckpointScheduler should create checkpoint without requiring another write"
        )
        # Clean up policy
        set_checkpoint_policy(None)
