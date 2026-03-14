"""Tests for checkpoints and sinks."""
import tempfile
import os
from anip_server.checkpoint import CheckpointPolicy, CheckpointScheduler
from anip_server.sinks import LocalFileSink


def test_checkpoint_policy_entry_count():
    policy = CheckpointPolicy(entry_count=5)
    assert not policy.should_checkpoint(4)
    assert policy.should_checkpoint(5)


def test_checkpoint_policy_no_threshold():
    policy = CheckpointPolicy()
    assert not policy.should_checkpoint(1000)


def test_local_file_sink():
    with tempfile.TemporaryDirectory() as tmpdir:
        sink = LocalFileSink(tmpdir)
        sink.publish({
            "body": {"checkpoint_id": "ckpt-001", "merkle_root": "sha256:abc"},
            "signature": "header..sig",
        })
        files = os.listdir(tmpdir)
        assert len(files) == 1
        assert files[0] == "ckpt-001.json"
