"""Tests for checkpoint sinks."""
import json
import os
import tempfile

from anip_server.primitives.sinks import LocalFileSink


class TestLocalFileSink:
    def test_publish_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sink = LocalFileSink(tmpdir)
            signed_ckpt = {
                "body": {
                    "checkpoint_id": "ckpt-001",
                    "merkle_root": "sha256:abc123",
                    "timestamp": "2026-03-12T18:00:00Z",
                },
                "signature": "header..sig",
            }
            sink.publish(signed_ckpt)
            files = os.listdir(tmpdir)
            assert len(files) == 1
            with open(os.path.join(tmpdir, files[0])) as f:
                stored = json.load(f)
            assert stored["body"]["checkpoint_id"] == "ckpt-001"
            assert stored["signature"] == "header..sig"

    def test_publish_multiple_creates_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sink = LocalFileSink(tmpdir)
            for i in range(3):
                sink.publish({
                    "body": {"checkpoint_id": f"ckpt-{i:03d}", "merkle_root": f"sha256:{i}"},
                    "signature": f"header..sig{i}",
                })
            assert len(os.listdir(tmpdir)) == 3
