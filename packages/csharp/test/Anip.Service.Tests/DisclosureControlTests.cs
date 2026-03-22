using Anip.Service;

namespace Anip.Service.Tests;

public class DisclosureControlTests
{
    [Fact]
    public void FixedMode_Full_PassesThrough()
    {
        Assert.Equal("full", DisclosureControl.Resolve("full", null, null));
    }

    [Fact]
    public void FixedMode_Reduced_PassesThrough()
    {
        Assert.Equal("reduced", DisclosureControl.Resolve("reduced", null, null));
    }

    [Fact]
    public void FixedMode_Redacted_PassesThrough()
    {
        Assert.Equal("redacted", DisclosureControl.Resolve("redacted", null, null));
    }

    [Fact]
    public void PolicyMode_NullPolicy_DefaultsToRedacted()
    {
        Assert.Equal("redacted", DisclosureControl.Resolve("policy", null, null));
    }

    [Fact]
    public void PolicyMode_ExplicitCallerClass()
    {
        var claims = new Dictionary<string, object?>
        {
            ["anip:caller_class"] = "internal",
        };
        var policy = new Dictionary<string, string>
        {
            ["internal"] = "full",
            ["default"] = "redacted",
        };

        Assert.Equal("full", DisclosureControl.Resolve("policy", claims, policy));
    }

    [Fact]
    public void PolicyMode_ScopeDerived_AuditFull()
    {
        var claims = new Dictionary<string, object?>
        {
            ["scope"] = new List<string> { "audit:full", "data" },
        };
        var policy = new Dictionary<string, string>
        {
            ["audit_full"] = "full",
            ["default"] = "redacted",
        };

        Assert.Equal("full", DisclosureControl.Resolve("policy", claims, policy));
    }

    [Fact]
    public void PolicyMode_NoClaims_FallsToDefault()
    {
        var policy = new Dictionary<string, string>
        {
            ["internal"] = "full",
            ["default"] = "reduced",
        };

        Assert.Equal("reduced", DisclosureControl.Resolve("policy", null, policy));
    }

    [Fact]
    public void PolicyMode_UnknownClass_FallsToDefault()
    {
        var claims = new Dictionary<string, object?>
        {
            ["anip:caller_class"] = "unknown_class",
        };
        var policy = new Dictionary<string, string>
        {
            ["internal"] = "full",
            ["default"] = "reduced",
        };

        Assert.Equal("reduced", DisclosureControl.Resolve("policy", claims, policy));
    }

    [Fact]
    public void PolicyMode_NoDefault_FallsToRedacted()
    {
        var claims = new Dictionary<string, object?>
        {
            ["anip:caller_class"] = "unknown_class",
        };
        var policy = new Dictionary<string, string>
        {
            ["internal"] = "full",
        };

        Assert.Equal("redacted", DisclosureControl.Resolve("policy", claims, policy));
    }
}
