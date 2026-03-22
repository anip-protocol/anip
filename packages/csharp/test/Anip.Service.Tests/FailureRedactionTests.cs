using Anip.Service;

namespace Anip.Service.Tests;

public class FailureRedactionTests
{
    [Fact]
    public void Full_ReturnsAsIs()
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = "scope_insufficient",
            ["detail"] = "delegation chain lacks scope(s): data.write",
            ["retry"] = false,
        };

        var result = FailureRedaction.Redact(failure, "full");

        Assert.Equal("scope_insufficient", result["type"]);
        Assert.Equal("delegation chain lacks scope(s): data.write", result["detail"]);
        Assert.Equal(false, result["retry"]);
    }

    [Fact]
    public void Full_DoesNotMutateOriginal()
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = "scope_insufficient",
            ["detail"] = "original detail",
        };

        var result = FailureRedaction.Redact(failure, "full");
        result["detail"] = "modified";

        Assert.Equal("original detail", failure["detail"]);
    }

    [Fact]
    public void Reduced_TruncatesDetail()
    {
        var longDetail = new string('x', 300);
        var failure = new Dictionary<string, object?>
        {
            ["type"] = "scope_insufficient",
            ["detail"] = longDetail,
        };

        var result = FailureRedaction.Redact(failure, "reduced");

        var detail = (string)result["detail"]!;
        Assert.Equal(200, detail.Length);
    }

    [Fact]
    public void Reduced_ShortDetailUnchanged()
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = "scope_insufficient",
            ["detail"] = "short",
        };

        var result = FailureRedaction.Redact(failure, "reduced");
        Assert.Equal("short", result["detail"]);
    }

    [Fact]
    public void Reduced_NullsGrantableBy()
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = "scope_insufficient",
            ["detail"] = "details",
            ["resolution"] = new Dictionary<string, object?>
            {
                ["action"] = "request_scope_grant",
                ["grantable_by"] = "admin@example.com",
            },
        };

        var result = FailureRedaction.Redact(failure, "reduced");
        var resolution = (Dictionary<string, object?>)result["resolution"]!;
        Assert.Equal("request_scope_grant", resolution["action"]);
        Assert.Null(resolution["grantable_by"]);
    }

    [Fact]
    public void Redacted_ReplacesDetailWithGeneric()
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = "scope_insufficient",
            ["detail"] = "delegation chain lacks scope(s): data.write, admin.users",
        };

        var result = FailureRedaction.Redact(failure, "redacted");
        Assert.Equal("Insufficient scope for this capability", result["detail"]);
    }

    [Fact]
    public void Redacted_UnknownType_FallsBackToGeneric()
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = "some_unknown_type",
            ["detail"] = "something went wrong",
        };

        var result = FailureRedaction.Redact(failure, "redacted");
        Assert.Equal("Request failed", result["detail"]);
    }

    [Fact]
    public void Redacted_TypePreserved()
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = "invalid_token",
            ["detail"] = "secret details here",
        };

        var result = FailureRedaction.Redact(failure, "redacted");
        Assert.Equal("invalid_token", result["type"]);
    }

    [Fact]
    public void Redacted_RetryPreserved()
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = "unavailable",
            ["detail"] = "secret details",
            ["retry"] = true,
        };

        var result = FailureRedaction.Redact(failure, "redacted");
        Assert.Equal(true, result["retry"]);
    }

    [Fact]
    public void Redacted_ResolutionOnlyKeepsAction()
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = "scope_insufficient",
            ["detail"] = "details",
            ["resolution"] = new Dictionary<string, object?>
            {
                ["action"] = "request_scope_grant",
                ["requires"] = "data.write",
                ["grantable_by"] = "admin@example.com",
                ["estimated_availability"] = "immediate",
            },
        };

        var result = FailureRedaction.Redact(failure, "redacted");
        var resolution = (Dictionary<string, object?>)result["resolution"]!;
        Assert.Equal("request_scope_grant", resolution["action"]);
        Assert.Null(resolution["requires"]);
        Assert.Null(resolution["grantable_by"]);
        Assert.Null(resolution["estimated_availability"]);
    }
}
