using Xunit;
using GTMOperatorContract20260512235040;

namespace GTMOperatorContract20260512235040.Tests;

public class GeneratedCapabilitiesTests
{
    [Fact]
    public void CreatesCapabilityDefinitions()
    {
        var capabilities = GeneratedCapabilities.CreateAll(BackendAdapter.Default);
        Assert.NotEmpty(capabilities);
        Assert.Equal("gtm.pipeline_summary", capabilities.First().Declaration.Name);
    }
}
