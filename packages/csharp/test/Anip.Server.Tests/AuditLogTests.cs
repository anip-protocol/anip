using Anip.Core;
using Anip.Crypto;
using Anip.Server;
using Xunit;

namespace Anip.Server.Tests;

public class AuditLogTests : IDisposable
{
    private readonly KeyManager _keys;
    private readonly SqliteStorage _storage;

    public AuditLogTests()
    {
        _keys = new KeyManager();
        _storage = new SqliteStorage(":memory:");
    }

    public void Dispose()
    {
        _storage.Dispose();
    }

    [Fact]
    public void AppendWithSignature()
    {
        var entry = new AuditEntry
        {
            Capability = "summarize",
            RootPrincipal = "user@example.com",
            Success = true
        };

        var appended = AuditLog.AppendAudit(_keys, _storage, entry);

        Assert.Equal(1, appended.SequenceNumber);
        Assert.NotNull(appended.Signature);
        Assert.NotEmpty(appended.Signature!);
        Assert.NotNull(appended.Timestamp);
        Assert.NotEmpty(appended.Timestamp);
        Assert.Equal("sha256:0", appended.PreviousHash);
    }

    [Fact]
    public void AppendSetsTimestamp()
    {
        var entry = new AuditEntry
        {
            Capability = "test",
            RootPrincipal = "user@example.com",
            Success = true
        };

        var before = DateTime.UtcNow;
        var appended = AuditLog.AppendAudit(_keys, _storage, entry);
        var after = DateTime.UtcNow;

        Assert.NotEmpty(appended.Timestamp);
        var ts = DateTimeOffset.Parse(appended.Timestamp);
        Assert.InRange(ts, before, after.AddSeconds(1));
    }

    [Fact]
    public void AppendPreservesExistingTimestamp()
    {
        var entry = new AuditEntry
        {
            Timestamp = "2025-06-15T12:00:00Z",
            Capability = "test",
            RootPrincipal = "user@example.com",
            Success = true
        };

        var appended = AuditLog.AppendAudit(_keys, _storage, entry);
        Assert.Equal("2025-06-15T12:00:00Z", appended.Timestamp);
    }

    [Fact]
    public void QueryByRootPrincipal()
    {
        AuditLog.AppendAudit(_keys, _storage, new AuditEntry
        {
            Capability = "summarize",
            RootPrincipal = "user-a@example.com",
            Success = true
        });

        AuditLog.AppendAudit(_keys, _storage, new AuditEntry
        {
            Capability = "translate",
            RootPrincipal = "user-b@example.com",
            Success = true
        });

        AuditLog.AppendAudit(_keys, _storage, new AuditEntry
        {
            Capability = "classify",
            RootPrincipal = "user-a@example.com",
            Success = true
        });

        var response = AuditLog.QueryAudit(_storage, "user-a@example.com", new AuditFilters());

        Assert.Equal(2, response.Entries.Count);
        Assert.All(response.Entries, e => Assert.Equal("user-a@example.com", e.RootPrincipal));
    }

    [Fact]
    public void HashChainIntegrity()
    {
        var entry1 = AuditLog.AppendAudit(_keys, _storage, new AuditEntry
        {
            Capability = "test-1",
            RootPrincipal = "user@example.com",
            Success = true
        });

        var entry2 = AuditLog.AppendAudit(_keys, _storage, new AuditEntry
        {
            Capability = "test-2",
            RootPrincipal = "user@example.com",
            Success = true
        });

        var entry3 = AuditLog.AppendAudit(_keys, _storage, new AuditEntry
        {
            Capability = "test-3",
            RootPrincipal = "user@example.com",
            Success = true
        });

        // Verify chain: entry2.previous_hash should be hash of entry1.
        var hash1 = HashChain.ComputeEntryHash(entry1);
        Assert.Equal(hash1, entry2.PreviousHash);

        // Verify chain: entry3.previous_hash should be hash of entry2.
        var hash2 = HashChain.ComputeEntryHash(entry2);
        Assert.Equal(hash2, entry3.PreviousHash);

        // All hashes should start with "sha256:".
        Assert.StartsWith("sha256:", entry1.PreviousHash!);
        Assert.StartsWith("sha256:", entry2.PreviousHash!);
        Assert.StartsWith("sha256:", entry3.PreviousHash!);
    }

    [Fact]
    public void SignatureIsStoredInDatabase()
    {
        var appended = AuditLog.AppendAudit(_keys, _storage, new AuditEntry
        {
            Capability = "test",
            RootPrincipal = "user@example.com",
            Success = true
        });

        // Load from storage and check signature is persisted.
        var entries = _storage.GetAuditEntriesRange(appended.SequenceNumber, appended.SequenceNumber);
        Assert.Single(entries);
        Assert.Equal(appended.Signature, entries[0].Signature);
    }
}
