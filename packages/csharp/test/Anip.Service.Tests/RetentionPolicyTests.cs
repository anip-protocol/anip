using Anip.Service;

namespace Anip.Service.Tests;

public class RetentionPolicyTests
{
    [Fact]
    public void DefaultTiers_HighRiskSuccess_Long()
    {
        var rp = new RetentionPolicy();
        Assert.Equal("long", rp.ResolveTier("high_risk_success"));
    }

    [Fact]
    public void DefaultTiers_HighRiskDenial_Medium()
    {
        var rp = new RetentionPolicy();
        Assert.Equal("medium", rp.ResolveTier("high_risk_denial"));
    }

    [Fact]
    public void DefaultTiers_LowRiskSuccess_Short()
    {
        var rp = new RetentionPolicy();
        Assert.Equal("short", rp.ResolveTier("low_risk_success"));
    }

    [Fact]
    public void DefaultTiers_MalformedOrSpam_Short()
    {
        var rp = new RetentionPolicy();
        Assert.Equal("short", rp.ResolveTier("malformed_or_spam"));
    }

    [Fact]
    public void DefaultTiers_RepeatedLowValue_AggregateOnly()
    {
        var rp = new RetentionPolicy();
        Assert.Equal("aggregate_only", rp.ResolveTier("repeated_low_value_denial"));
    }

    [Fact]
    public void DefaultTiers_Unknown_FallsBackToShort()
    {
        var rp = new RetentionPolicy();
        Assert.Equal("short", rp.ResolveTier("some_unknown_class"));
    }

    [Fact]
    public void ComputeExpiresAt_LongTier()
    {
        var rp = new RetentionPolicy();
        var now = new DateTime(2025, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var expires = rp.ComputeExpiresAt("long", now);
        Assert.Contains("2026-01-01", expires); // 365 days later
    }

    [Fact]
    public void ComputeExpiresAt_MediumTier()
    {
        var rp = new RetentionPolicy();
        var now = new DateTime(2025, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var expires = rp.ComputeExpiresAt("medium", now);
        Assert.Contains("2025-04-01", expires); // 90 days later
    }

    [Fact]
    public void ComputeExpiresAt_ShortTier()
    {
        var rp = new RetentionPolicy();
        var now = new DateTime(2025, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var expires = rp.ComputeExpiresAt("short", now);
        Assert.Contains("2025-01-08", expires); // 7 days later
    }

    [Fact]
    public void ComputeExpiresAt_UnknownTier_Empty()
    {
        var rp = new RetentionPolicy();
        var now = DateTime.UtcNow;
        var expires = rp.ComputeExpiresAt("unknown_tier", now);
        Assert.Equal("", expires);
    }

    [Fact]
    public void DefaultRetention_ReturnsMedium()
    {
        var rp = new RetentionPolicy();
        Assert.Equal("P90D", rp.DefaultRetention());
    }

    [Fact]
    public void CustomOverrides_ClassToTier()
    {
        var rp = new RetentionPolicy(
            classOverrides: new Dictionary<string, string>
            {
                ["high_risk_success"] = "medium"
            });
        Assert.Equal("medium", rp.ResolveTier("high_risk_success"));
        // Other defaults preserved.
        Assert.Equal("short", rp.ResolveTier("low_risk_success"));
    }

    [Fact]
    public void CustomOverrides_TierToDuration()
    {
        var rp = new RetentionPolicy(
            tierOverrides: new Dictionary<string, string>
            {
                ["medium"] = "P30D"
            });
        Assert.Equal("P30D", rp.DefaultRetention());

        var now = new DateTime(2025, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var expires = rp.ComputeExpiresAt("medium", now);
        Assert.Contains("2025-01-31", expires); // 30 days later
    }
}
