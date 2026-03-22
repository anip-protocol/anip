using Anip.Core;
using Anip.Crypto;
using Anip.Server;
using Xunit;

namespace Anip.Server.Tests;

public class CheckpointManagerTests : IDisposable
{
    private readonly KeyManager _keys;
    private readonly SqliteStorage _storage;
    private const string ServiceId = "svc-test";

    public CheckpointManagerTests()
    {
        _keys = new KeyManager();
        _storage = new SqliteStorage(":memory:");
    }

    public void Dispose()
    {
        _storage.Dispose();
    }

    private void AppendEntries(int count)
    {
        for (int i = 0; i < count; i++)
        {
            AuditLog.AppendAudit(_keys, _storage, new AuditEntry
            {
                Capability = $"cap-{i}",
                RootPrincipal = "user@example.com",
                Success = true
            });
        }
    }

    [Fact]
    public void CreateCheckpoint_NoEntries_ReturnsNull()
    {
        var cp = CheckpointManager.CreateCheckpoint(_keys, _storage, ServiceId);
        Assert.Null(cp);
    }

    [Fact]
    public void CreateCheckpoint_WithEntries()
    {
        AppendEntries(5);

        var cp = CheckpointManager.CreateCheckpoint(_keys, _storage, ServiceId);

        Assert.NotNull(cp);
        Assert.Equal("ckpt-1", cp.CheckpointId);
        Assert.Equal("0.3", cp.Version);
        Assert.Equal(ServiceId, cp.ServiceId);
        Assert.Equal(5, cp.EntryCount);
        Assert.Equal(1, cp.Range["first_sequence"]);
        Assert.Equal(5, cp.Range["last_sequence"]);
        Assert.StartsWith("sha256:", cp.MerkleRoot);
        Assert.Null(cp.PreviousCheckpoint);
    }

    [Fact]
    public void CreateCheckpoint_StoresMerkleRoot()
    {
        AppendEntries(3);

        var cp = CheckpointManager.CreateCheckpoint(_keys, _storage, ServiceId);

        Assert.NotNull(cp);
        Assert.NotEmpty(cp.MerkleRoot);
        Assert.StartsWith("sha256:", cp.MerkleRoot);

        // Stored in database.
        var stored = _storage.GetCheckpointById(cp.CheckpointId);
        Assert.NotNull(stored);
        Assert.Equal(cp.MerkleRoot, stored.MerkleRoot);
    }

    [Fact]
    public void CreateCheckpoint_SecondCheckpoint_LinksToPrevious()
    {
        AppendEntries(3);
        var cp1 = CheckpointManager.CreateCheckpoint(_keys, _storage, ServiceId);
        Assert.NotNull(cp1);

        AppendEntries(2);
        var cp2 = CheckpointManager.CreateCheckpoint(_keys, _storage, ServiceId);
        Assert.NotNull(cp2);

        Assert.Equal("ckpt-2", cp2.CheckpointId);
        Assert.NotNull(cp2.PreviousCheckpoint);
        Assert.StartsWith("sha256:", cp2.PreviousCheckpoint!);
        Assert.Equal(5, cp2.EntryCount);
        Assert.Equal(5, cp2.Range["last_sequence"]);
    }

    [Fact]
    public void CreateCheckpoint_NoNewEntries_ReturnsNull()
    {
        AppendEntries(3);
        CheckpointManager.CreateCheckpoint(_keys, _storage, ServiceId);

        // No new entries — should return null.
        var cp2 = CheckpointManager.CreateCheckpoint(_keys, _storage, ServiceId);
        Assert.Null(cp2);
    }

    [Fact]
    public void InclusionProof_FromCheckpoint()
    {
        AppendEntries(5);

        var cp = CheckpointManager.CreateCheckpoint(_keys, _storage, ServiceId);
        Assert.NotNull(cp);

        // Generate inclusion proof for each leaf.
        for (int i = 0; i < 5; i++)
        {
            var (proof, reason) = CheckpointManager.GenerateInclusionProof(_storage, cp, i);
            Assert.NotNull(proof);
            Assert.Null(reason);
            Assert.True(proof.Count > 0 || i == 0 && cp.EntryCount == 1);
        }
    }

    [Fact]
    public void InclusionProof_ExpiredEntries()
    {
        // Append entries with expiry.
        for (int i = 0; i < 3; i++)
        {
            AuditLog.AppendAudit(_keys, _storage, new AuditEntry
            {
                Capability = $"cap-{i}",
                RootPrincipal = "user@example.com",
                Success = true,
                ExpiresAt = "2025-01-01T00:00:00Z"
            });
        }

        var cp = CheckpointManager.CreateCheckpoint(_keys, _storage, ServiceId);
        Assert.NotNull(cp);

        // Delete expired entries.
        _storage.DeleteExpiredAuditEntries("2026-01-01T00:00:00Z");

        // Inclusion proof should return unavailable reason.
        var (proof, reason) = CheckpointManager.GenerateInclusionProof(_storage, cp, 0);
        Assert.Null(proof);
        Assert.Equal("audit_entries_expired", reason);
    }

    [Fact]
    public void InclusionProof_OutOfRange_Throws()
    {
        AppendEntries(3);
        var cp = CheckpointManager.CreateCheckpoint(_keys, _storage, ServiceId);
        Assert.NotNull(cp);

        Assert.Throws<ArgumentOutOfRangeException>(() =>
            CheckpointManager.GenerateInclusionProof(_storage, cp, 10));
    }

    [Fact]
    public void CheckpointMerkleRoot_MatchesManualTree()
    {
        // Append entries and build a manual Merkle tree to compare.
        AppendEntries(4);

        var entries = _storage.GetAuditEntriesRange(1, 4);
        var manualTree = new MerkleTree();
        foreach (var entry in entries)
        {
            manualTree.AddLeaf(HashChain.CanonicalBytes(entry));
        }

        var cp = CheckpointManager.CreateCheckpoint(_keys, _storage, ServiceId);
        Assert.NotNull(cp);

        Assert.Equal(manualTree.Root(), cp.MerkleRoot);
    }
}
