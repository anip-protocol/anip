using Xunit;
using GTMPipelineQ2Review;

namespace GTMPipelineQ2Review.Tests;

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
