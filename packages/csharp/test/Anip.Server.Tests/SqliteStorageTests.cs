using Anip.Core;
using Anip.Server;
using Xunit;

namespace Anip.Server.Tests;

public class SqliteStorageTests : IDisposable
{
    private readonly SqliteStorage _storage;

    public SqliteStorageTests()
    {
        _storage = new SqliteStorage(":memory:");
    }

    public void Dispose()
    {
        _storage.Dispose();
    }

    [Fact]
    public void StoreAndLoadToken()
    {
        var token = new DelegationToken
        {
            TokenId = "tok-001",
            Issuer = "svc-test",
            Subject = "user@example.com",
            Scope = new List<string> { "data:read" },
            Purpose = new Purpose { Capability = "summarize", TaskId = "task-001" },
            Expires = "2030-01-01T00:00:00Z",
            RootPrincipal = "user@example.com"
        };

        _storage.StoreToken(token);

        var loaded = _storage.LoadToken("tok-001");
        Assert.NotNull(loaded);
        Assert.Equal("tok-001", loaded.TokenId);
        Assert.Equal("svc-test", loaded.Issuer);
        Assert.Equal("user@example.com", loaded.Subject);
        Assert.Single(loaded.Scope);
        Assert.Equal("data:read", loaded.Scope[0]);
    }

    [Fact]
    public void LoadToken_NotFound_ReturnsNull()
    {
        var loaded = _storage.LoadToken("nonexistent");
        Assert.Null(loaded);
    }

    [Fact]
    public void AppendAndQueryAuditEntries()
    {
        var entry1 = new AuditEntry
        {
            Timestamp = "2025-01-01T00:00:00Z",
            Capability = "summarize",
            RootPrincipal = "user@example.com",
            Success = true
        };

        var entry2 = new AuditEntry
        {
            Timestamp = "2025-01-02T00:00:00Z",
            Capability = "translate",
            RootPrincipal = "user@example.com",
            Success = true
        };

        var appended1 = _storage.AppendAuditEntry(entry1);
        var appended2 = _storage.AppendAuditEntry(entry2);

        Assert.Equal(1, appended1.SequenceNumber);
        Assert.Equal(2, appended2.SequenceNumber);

        // First entry uses sentinel hash.
        Assert.Equal("sha256:0", appended1.PreviousHash);
        // Second entry uses hash of first entry.
        Assert.NotNull(appended2.PreviousHash);
        Assert.NotEqual("sha256:0", appended2.PreviousHash);
    }

    [Fact]
    public void AuditSequenceNumbering()
    {
        for (int i = 0; i < 5; i++)
        {
            var entry = new AuditEntry
            {
                Timestamp = $"2025-01-{i + 1:D2}T00:00:00Z",
                Capability = "test",
                RootPrincipal = "user@example.com",
                Success = true
            };
            _storage.AppendAuditEntry(entry);
        }

        var maxSeq = _storage.GetMaxAuditSequence();
        Assert.Equal(5, maxSeq);

        var range = _storage.GetAuditEntriesRange(2, 4);
        Assert.Equal(3, range.Count);
        Assert.Equal(2, range[0].SequenceNumber);
        Assert.Equal(4, range[2].SequenceNumber);
    }

    [Fact]
    public void AuditFiltering_ByCapability()
    {
        _storage.AppendAuditEntry(new AuditEntry
        {
            Timestamp = "2025-01-01T00:00:00Z",
            Capability = "summarize",
            RootPrincipal = "user@example.com",
            Success = true
        });
        _storage.AppendAuditEntry(new AuditEntry
        {
            Timestamp = "2025-01-02T00:00:00Z",
            Capability = "translate",
            RootPrincipal = "user@example.com",
            Success = true
        });
        _storage.AppendAuditEntry(new AuditEntry
        {
            Timestamp = "2025-01-03T00:00:00Z",
            Capability = "summarize",
            RootPrincipal = "user@example.com",
            Success = true
        });

        var results = _storage.QueryAuditEntries(new AuditFilters
        {
            Capability = "summarize"
        });

        Assert.Equal(2, results.Count);
        Assert.All(results, e => Assert.Equal("summarize", e.Capability));
    }

    [Fact]
    public void AuditFiltering_Since()
    {
        _storage.AppendAuditEntry(new AuditEntry
        {
            Timestamp = "2025-01-01T00:00:00Z",
            Capability = "test",
            RootPrincipal = "user@example.com",
            Success = true
        });
        _storage.AppendAuditEntry(new AuditEntry
        {
            Timestamp = "2025-06-01T00:00:00Z",
            Capability = "test",
            RootPrincipal = "user@example.com",
            Success = true
        });

        var results = _storage.QueryAuditEntries(new AuditFilters
        {
            Since = "2025-03-01T00:00:00Z"
        });

        Assert.Single(results);
        Assert.Equal("2025-06-01T00:00:00Z", results[0].Timestamp);
    }

    [Fact]
    public void AuditFiltering_Limit()
    {
        for (int i = 0; i < 10; i++)
        {
            _storage.AppendAuditEntry(new AuditEntry
            {
                Timestamp = $"2025-01-{i + 1:D2}T00:00:00Z",
                Capability = "test",
                RootPrincipal = "user@example.com",
                Success = true
            });
        }

        var results = _storage.QueryAuditEntries(new AuditFilters { Limit = 3 });
        Assert.Equal(3, results.Count);
    }

    [Fact]
    public void LeaseAcquireAndRelease()
    {
        // Acquire a lease.
        var acquired = _storage.TryAcquireExclusive("my-key", "holder-1", 60);
        Assert.True(acquired);

        // Second holder can't acquire.
        var blocked = _storage.TryAcquireExclusive("my-key", "holder-2", 60);
        Assert.False(blocked);

        // Same holder can re-acquire.
        var reacquired = _storage.TryAcquireExclusive("my-key", "holder-1", 60);
        Assert.True(reacquired);

        // Release.
        _storage.ReleaseExclusive("my-key", "holder-1");

        // Now second holder can acquire.
        var afterRelease = _storage.TryAcquireExclusive("my-key", "holder-2", 60);
        Assert.True(afterRelease);
    }

    [Fact]
    public void LeaderLease()
    {
        var acquired = _storage.TryAcquireLeader("checkpoint", "node-1", 60);
        Assert.True(acquired);

        var blocked = _storage.TryAcquireLeader("checkpoint", "node-2", 60);
        Assert.False(blocked);

        _storage.ReleaseLeader("checkpoint", "node-1");

        var afterRelease = _storage.TryAcquireLeader("checkpoint", "node-2", 60);
        Assert.True(afterRelease);
    }

    [Fact]
    public void DeleteExpiredEntries()
    {
        _storage.AppendAuditEntry(new AuditEntry
        {
            Timestamp = "2025-01-01T00:00:00Z",
            Capability = "test",
            RootPrincipal = "user@example.com",
            Success = true,
            ExpiresAt = "2025-06-01T00:00:00Z"
        });
        _storage.AppendAuditEntry(new AuditEntry
        {
            Timestamp = "2025-01-02T00:00:00Z",
            Capability = "test",
            RootPrincipal = "user@example.com",
            Success = true,
            ExpiresAt = "2030-01-01T00:00:00Z"
        });
        _storage.AppendAuditEntry(new AuditEntry
        {
            Timestamp = "2025-01-03T00:00:00Z",
            Capability = "test",
            RootPrincipal = "user@example.com",
            Success = true
            // No ExpiresAt — should not be deleted.
        });

        var deleted = _storage.DeleteExpiredAuditEntries("2026-01-01T00:00:00Z");
        Assert.Equal(1, deleted);

        // Verify remaining entries.
        var remaining = _storage.GetAuditEntriesRange(1, 100);
        Assert.Equal(2, remaining.Count);
    }

    [Fact]
    public void StoreAndListCheckpoints()
    {
        var cp = new Checkpoint
        {
            Version = "0.3",
            ServiceId = "svc-test",
            CheckpointId = "ckpt-1",
            Range = new Dictionary<string, int> { ["first_sequence"] = 1, ["last_sequence"] = 10 },
            MerkleRoot = "sha256:abc123",
            Timestamp = "2025-01-01T00:00:00Z",
            EntryCount = 10
        };

        _storage.StoreCheckpoint(cp, "sig-test");

        var list = _storage.ListCheckpoints(10);
        Assert.Single(list);
        Assert.Equal("ckpt-1", list[0].CheckpointId);
        Assert.Equal(10, list[0].EntryCount);
    }

    [Fact]
    public void GetCheckpointById()
    {
        var cp = new Checkpoint
        {
            Version = "0.3",
            ServiceId = "svc-test",
            CheckpointId = "ckpt-42",
            Range = new Dictionary<string, int> { ["first_sequence"] = 1, ["last_sequence"] = 5 },
            MerkleRoot = "sha256:deadbeef",
            Timestamp = "2025-01-01T00:00:00Z",
            EntryCount = 5
        };

        _storage.StoreCheckpoint(cp, "sig-42");

        var found = _storage.GetCheckpointById("ckpt-42");
        Assert.NotNull(found);
        Assert.Equal("ckpt-42", found.CheckpointId);

        var notFound = _storage.GetCheckpointById("nonexistent");
        Assert.Null(notFound);
    }

    [Fact]
    public void UpdateAuditSignature()
    {
        var entry = new AuditEntry
        {
            Timestamp = "2025-01-01T00:00:00Z",
            Capability = "test",
            RootPrincipal = "user@example.com",
            Success = true
        };

        var appended = _storage.AppendAuditEntry(entry);
        Assert.Null(appended.Signature);

        _storage.UpdateAuditSignature(appended.SequenceNumber, "test-signature");

        // Verify the signature is persisted in the data blob.
        var entries = _storage.GetAuditEntriesRange(appended.SequenceNumber, appended.SequenceNumber);
        Assert.Single(entries);
        Assert.Equal("test-signature", entries[0].Signature);
    }

    [Fact]
    public void GetMaxAuditSequence_Empty()
    {
        var maxSeq = _storage.GetMaxAuditSequence();
        Assert.Equal(0, maxSeq);
    }
}
