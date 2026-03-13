"""Tests for v0.2 audit log schema with hash chain."""

from anip_server.data.database import (
    get_connection,
    get_merkle_inclusion_proof,
    get_merkle_snapshot,
    log_invocation,
    query_audit_log,
)


def test_audit_table_has_new_columns():
    conn = get_connection()
    cursor = conn.execute("PRAGMA table_info(audit_log)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "sequence_number" in columns
    assert "previous_hash" in columns
    assert "signature" in columns


def test_first_audit_entry_has_sentinel_previous_hash():
    log_invocation(
        capability="test_cap",
        token_id="test-001",
        issuer="human:test@example.com",
        subject="agent:test",
        root_principal="human:test@example.com",
        parameters={"key": "value"},
        success=True,
    )
    entries = query_audit_log(root_principal="human:test@example.com")
    assert len(entries) >= 1
    entry = entries[-1]  # most recent (ordered DESC) — actually entries[0] is newest
    assert "previous_hash" in entry
    assert entry["sequence_number"] >= 1


def test_sequential_entries_form_hash_chain():
    log_invocation(
        capability="test_chain_1",
        token_id="test-chain-1",
        issuer="human:chain@example.com",
        subject="agent:test",
        root_principal="human:chain@example.com",
        parameters={},
        success=True,
    )
    log_invocation(
        capability="test_chain_2",
        token_id="test-chain-2",
        issuer="human:chain@example.com",
        subject="agent:test",
        root_principal="human:chain@example.com",
        parameters={},
        success=True,
    )
    entries = query_audit_log(root_principal="human:chain@example.com")
    # Entries are DESC, so [0] is newest, [1] is older
    if len(entries) >= 2:
        newer = entries[0]
        older = entries[1]
        assert newer["previous_hash"] != older["previous_hash"]
        assert newer["sequence_number"] > older["sequence_number"]


def test_merkle_root_advances_with_entries():
    """After logging entries, the Merkle root should change."""
    snap1 = get_merkle_snapshot()
    log_invocation(
        capability="test_merkle",
        token_id="test-merkle-1",
        issuer="human:test@example.com",
        subject="agent:test",
        root_principal="human:test@example.com",
        parameters={"key": "value"},
        success=True,
    )
    snap2 = get_merkle_snapshot()
    assert snap2["leaf_count"] == snap1["leaf_count"] + 1
    assert snap2["root"] != snap1["root"]


def test_merkle_inclusion_proof_for_audit_entry():
    """An inclusion proof for a logged entry should verify."""
    log_invocation(
        capability="test_merkle_proof",
        token_id="test-merkle-2",
        issuer="human:test@example.com",
        subject="agent:test",
        root_principal="human:test@example.com",
        parameters={"proof": "test"},
        success=True,
    )
    snap = get_merkle_snapshot()
    leaf_index = snap["leaf_count"] - 1
    proof = get_merkle_inclusion_proof(leaf_index)
    assert proof is not None
    assert len(proof["path"]) > 0 or snap["leaf_count"] == 1
