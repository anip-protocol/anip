using Xunit;
using notiongovernedfrontingshowcase;

namespace notiongovernedfrontingshowcase.Tests;

public class GeneratedCapabilitiesTests
{
    [Fact]
    public void CreatesCapabilityDefinitions()
    {
        var capabilities = GeneratedCapabilities.CreateAll(BackendAdapter.Default);
        Assert.NotEmpty(capabilities);
        Assert.Equal("notion.workspace.search_context", capabilities.First().Declaration.Name);
    }
}
