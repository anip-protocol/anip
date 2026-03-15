"""Backend compliance test suite for StorageBackend implementations."""
import asyncio
from typing import Any


async def compliance_token_roundtrip(storage) -> None:
    """Token store/load roundtrip."""
    token = {"token_id": "tok-c1", "issuer": "svc", "subject": "agent",
             "scope": ["a.b"], "purpose": {"capability": "c", "parameters": {}, "task_id": "t"},
             "parent": None, "expires": "2099-01-01T00:00:00Z",
             "constraints": {"max_delegation_depth": 3, "concurrent_branches": "allowed"},
             "root_principal": "human:alice"}
    await storage.store_token(token)
    loaded = await storage.load_token("tok-c1")
    assert loaded is not None
    assert loaded["token_id"] == "tok-c1"
    assert loaded["scope"] == ["a.b"]


async def compliance_token_not_found(storage) -> None:
    """load_token returns None for unknown ID."""
    assert await storage.load_token("nonexistent") is None


async def compliance_audit_roundtrip(storage) -> None:
    """Audit entry store and query."""
    entry = {"sequence_number": 1, "timestamp": "2026-01-01T00:00:00Z",
             "capability": "search", "token_id": "tok-1",
             "root_principal": "human:alice", "success": True,
             "invocation_id": "inv-aabbccddeeff", "client_reference_id": "ref-1",
             "previous_hash": "sha256:0", "signature": None}
    await storage.store_audit_entry(entry)
    results = await storage.query_audit_entries(capability="search")
    assert len(results) >= 1
    assert results[0]["capability"] == "search"


async def compliance_audit_lineage_filters(storage) -> None:
    """Audit query by invocation_id and client_reference_id."""
    for i in range(3):
        await storage.store_audit_entry({
            "sequence_number": i + 1, "timestamp": f"2026-01-0{i+1}T00:00:00Z",
            "capability": "cap", "root_principal": "human:a", "success": True,
            "invocation_id": f"inv-{'0' * 11}{i}", "client_reference_id": "ref-shared",
            "previous_hash": "sha256:0", "signature": None})
    by_inv = await storage.query_audit_entries(invocation_id="inv-000000000001")
    assert len(by_inv) == 1
    by_ref = await storage.query_audit_entries(client_reference_id="ref-shared")
    assert len(by_ref) == 3


async def compliance_audit_ordering(storage) -> None:
    """Audit entries maintain insertion order by sequence number."""
    for i in range(5):
        await storage.store_audit_entry({
            "sequence_number": i + 1, "timestamp": f"2026-01-0{i+1}T00:00:00Z",
            "capability": "cap", "root_principal": "human:a", "success": True,
            "previous_hash": "sha256:0", "signature": None})
    entries = await storage.query_audit_entries(root_principal="human:a", limit=10)
    seq_nums = [e["sequence_number"] for e in entries]
    # Descending order (most recent first)
    assert seq_nums == sorted(seq_nums, reverse=True)


async def compliance_audit_concurrent_ordering(storage) -> None:
    """Audit insertion ordering under concurrent calls."""
    async def insert(seq: int):
        await storage.store_audit_entry({
            "sequence_number": seq, "timestamp": "2026-01-01T00:00:00Z",
            "capability": "cap", "root_principal": "human:a", "success": True,
            "previous_hash": "sha256:0", "signature": None})

    await asyncio.gather(*[insert(i + 1) for i in range(20)])
    entries = await storage.query_audit_entries(root_principal="human:a", limit=100)
    assert len(entries) == 20
    seq_nums = [e["sequence_number"] for e in entries]
    assert seq_nums == sorted(seq_nums, reverse=True)
    last = await storage.get_last_audit_entry()
    assert last is not None
    assert last["sequence_number"] == 20


async def compliance_checkpoint_roundtrip(storage) -> None:
    """Checkpoint store/load roundtrip."""
    body = {"checkpoint_id": "cp-1", "merkle_root": "sha256:abc",
            "range": {"first_sequence": 1, "last_sequence": 5},
            "timestamp": "2026-01-01T00:00:00Z", "entry_count": 5}
    await storage.store_checkpoint(body, "sig-123")
    loaded = await storage.get_checkpoint_by_id("cp-1")
    assert loaded is not None
    assert loaded["checkpoint_id"] == "cp-1"
    assert loaded["merkle_root"] == "sha256:abc"


async def compliance_checkpoint_not_found(storage) -> None:
    """get_checkpoint_by_id returns None for unknown ID."""
    assert await storage.get_checkpoint_by_id("nonexistent") is None


async def compliance_checkpoint_listing(storage) -> None:
    """Checkpoint listing respects limit."""
    for i in range(5):
        await storage.store_checkpoint(
            {"checkpoint_id": f"cp-{i}", "merkle_root": f"sha256:{i}", "sequence_number": i + 1},
            f"sig-{i}")
    results = await storage.get_checkpoints(limit=3)
    assert len(results) == 3


async def compliance_audit_entries_range(storage) -> None:
    """get_audit_entries_range returns entries between sequence numbers."""
    for i in range(10):
        await storage.store_audit_entry({
            "sequence_number": i + 1, "timestamp": f"2026-01-{i+1:02d}T00:00:00Z",
            "capability": "cap", "root_principal": "human:a", "success": True,
            "previous_hash": "sha256:0", "signature": None})
    entries = await storage.get_audit_entries_range(3, 7)
    seq_nums = [e["sequence_number"] for e in entries]
    assert all(3 <= s <= 7 for s in seq_nums)


# Collected list for parametrize
ALL_COMPLIANCE_TESTS = [
    compliance_token_roundtrip,
    compliance_token_not_found,
    compliance_audit_roundtrip,
    compliance_audit_lineage_filters,
    compliance_audit_ordering,
    compliance_audit_concurrent_ordering,
    compliance_checkpoint_roundtrip,
    compliance_checkpoint_not_found,
    compliance_checkpoint_listing,
    compliance_audit_entries_range,
]
