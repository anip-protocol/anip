using Anip.Service;

namespace Anip.Service.Tests;

public class AuditAggregatorTests
{
    [Fact]
    public void SingleEvent_PassesThrough()
    {
        var aggregator = new AuditAggregator(60);

        var evt = new Dictionary<string, object?>
        {
            ["actor_key"] = "user1",
            ["capability"] = "cap1",
            ["failure_type"] = "invalid_token",
            ["timestamp"] = "2025-01-01T00:00:10+00:00",
        };

        aggregator.Submit(evt);

        // Flush after window closes (60 seconds).
        var flushTime = new DateTimeOffset(2025, 1, 1, 0, 1, 1, TimeSpan.Zero);
        var results = aggregator.Flush(flushTime);

        Assert.Single(results);
        Assert.IsType<Dictionary<string, object?>>(results[0]);
    }

    [Fact]
    public void MultipleEvents_SameKey_Aggregated()
    {
        var aggregator = new AuditAggregator(60);

        for (int i = 0; i < 3; i++)
        {
            aggregator.Submit(new Dictionary<string, object?>
            {
                ["actor_key"] = "user1",
                ["capability"] = "cap1",
                ["failure_type"] = "invalid_token",
                ["timestamp"] = $"2025-01-01T00:00:{10 + i:D2}+00:00",
                ["detail"] = "token error",
            });
        }

        var flushTime = new DateTimeOffset(2025, 1, 1, 0, 1, 1, TimeSpan.Zero);
        var results = aggregator.Flush(flushTime);

        Assert.Single(results);
        var aggregated = Assert.IsType<AggregatedEntry>(results[0]);
        Assert.Equal(3, aggregated.Count);
        Assert.Equal("repeated_low_value_denial", aggregated.EventClass);
        Assert.Equal("aggregate_only", aggregated.RetentionTier);
        Assert.Equal("user1", aggregated.GroupingKey["actor_key"]);
        Assert.Equal("cap1", aggregated.GroupingKey["capability"]);
        Assert.Equal("invalid_token", aggregated.GroupingKey["failure_type"]);
        Assert.Equal("token error", aggregated.RepresentativeDetail);
    }

    [Fact]
    public void DifferentKeys_SeparateBuckets()
    {
        var aggregator = new AuditAggregator(60);

        aggregator.Submit(new Dictionary<string, object?>
        {
            ["actor_key"] = "user1",
            ["capability"] = "cap1",
            ["failure_type"] = "invalid_token",
            ["timestamp"] = "2025-01-01T00:00:10+00:00",
        });

        aggregator.Submit(new Dictionary<string, object?>
        {
            ["actor_key"] = "user2",
            ["capability"] = "cap1",
            ["failure_type"] = "invalid_token",
            ["timestamp"] = "2025-01-01T00:00:15+00:00",
        });

        var flushTime = new DateTimeOffset(2025, 1, 1, 0, 1, 1, TimeSpan.Zero);
        var results = aggregator.Flush(flushTime);

        // Two separate events (one per bucket, each with single event).
        Assert.Equal(2, results.Count);
        Assert.All(results, r => Assert.IsType<Dictionary<string, object?>>(r));
    }

    [Fact]
    public void OpenWindows_NotFlushed()
    {
        var aggregator = new AuditAggregator(60);

        aggregator.Submit(new Dictionary<string, object?>
        {
            ["actor_key"] = "user1",
            ["capability"] = "cap1",
            ["failure_type"] = "invalid_token",
            ["timestamp"] = "2025-01-01T00:00:10+00:00",
        });

        // Flush before window closes.
        var flushTime = new DateTimeOffset(2025, 1, 1, 0, 0, 30, TimeSpan.Zero);
        var results = aggregator.Flush(flushTime);

        Assert.Empty(results);
    }

    [Fact]
    public void AggregatedEntry_ToAuditDict()
    {
        var entry = new AggregatedEntry
        {
            EventClass = "repeated_low_value_denial",
            RetentionTier = "aggregate_only",
            GroupingKey = new Dictionary<string, string>
            {
                ["actor_key"] = "user1",
                ["capability"] = "cap1",
                ["failure_type"] = "invalid_token",
            },
            WindowStart = "2025-01-01T00:00:00Z",
            WindowEnd = "2025-01-01T00:01:00Z",
            Count = 5,
            FirstSeen = "2025-01-01T00:00:10Z",
            LastSeen = "2025-01-01T00:00:50Z",
            RepresentativeDetail = "token error",
        };

        var dict = entry.ToAuditDict();

        Assert.Equal("aggregated", dict["entry_type"]);
        Assert.Equal(5, dict["count"]);
        Assert.Equal("cap1", dict["capability"]);
        Assert.Equal("invalid_token", dict["failure_type"]);
        Assert.Equal(false, dict["success"]);
    }
}
