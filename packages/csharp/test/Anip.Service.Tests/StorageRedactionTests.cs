using Anip.Service;

namespace Anip.Service.Tests;

public class StorageRedactionTests
{
    [Fact]
    public void LowRiskSuccess_StripsParameters()
    {
        var entry = new Dictionary<string, object?>
        {
            ["event_class"] = "low_risk_success",
            ["parameters"] = new Dictionary<string, object?> { ["query"] = "test" },
        };

        var result = StorageRedaction.RedactEntry(entry);

        Assert.Null(result["parameters"]);
        Assert.Equal(true, result["storage_redacted"]);
    }

    [Fact]
    public void MalformedOrSpam_StripsParameters()
    {
        var entry = new Dictionary<string, object?>
        {
            ["event_class"] = "malformed_or_spam",
            ["parameters"] = new Dictionary<string, object?> { ["bad"] = "data" },
        };

        var result = StorageRedaction.RedactEntry(entry);

        Assert.Null(result["parameters"]);
        Assert.Equal(true, result["storage_redacted"]);
    }

    [Fact]
    public void RepeatedLowValueDenial_StripsParameters()
    {
        var entry = new Dictionary<string, object?>
        {
            ["event_class"] = "repeated_low_value_denial",
            ["parameters"] = new Dictionary<string, object?> { ["x"] = "y" },
        };

        var result = StorageRedaction.RedactEntry(entry);

        Assert.Null(result["parameters"]);
        Assert.Equal(true, result["storage_redacted"]);
    }

    [Fact]
    public void HighRiskSuccess_PreservesParameters()
    {
        var parameters = new Dictionary<string, object?> { ["amount"] = 100 };
        var entry = new Dictionary<string, object?>
        {
            ["event_class"] = "high_risk_success",
            ["parameters"] = parameters,
        };

        var result = StorageRedaction.RedactEntry(entry);

        Assert.Same(parameters, result["parameters"]);
        Assert.Equal(false, result["storage_redacted"]);
    }

    [Fact]
    public void HighRiskDenial_PreservesParameters()
    {
        var parameters = new Dictionary<string, object?> { ["attempt"] = "denied" };
        var entry = new Dictionary<string, object?>
        {
            ["event_class"] = "high_risk_denial",
            ["parameters"] = parameters,
        };

        var result = StorageRedaction.RedactEntry(entry);

        Assert.Same(parameters, result["parameters"]);
        Assert.Equal(false, result["storage_redacted"]);
    }

    [Fact]
    public void DoesNotMutateOriginal()
    {
        var parameters = new Dictionary<string, object?> { ["query"] = "test" };
        var entry = new Dictionary<string, object?>
        {
            ["event_class"] = "low_risk_success",
            ["parameters"] = parameters,
        };

        StorageRedaction.RedactEntry(entry);

        // Original should still have parameters.
        Assert.Same(parameters, entry["parameters"]);
        Assert.False(entry.ContainsKey("storage_redacted"));
    }
}
