import os
os.environ.setdefault("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")

from studio.server.hashing import canonical_json, content_hash


def test_canonical_json_sorts_keys():
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_canonical_json_deterministic():
    d1 = {"x": {"b": 2, "a": 1}, "y": [3, 1]}
    d2 = {"y": [3, 1], "x": {"a": 1, "b": 2}}
    assert canonical_json(d1) == canonical_json(d2)


def test_content_hash_is_sha256():
    h = content_hash({"test": True})
    assert len(h) == 64  # SHA-256 hex = 64 chars
    assert h == content_hash({"test": True})  # deterministic


def test_content_hash_changes_on_different_data():
    assert content_hash({"a": 1}) != content_hash({"a": 2})
