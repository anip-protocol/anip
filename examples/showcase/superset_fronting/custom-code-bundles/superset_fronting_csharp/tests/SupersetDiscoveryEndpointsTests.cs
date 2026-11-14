using {{ANIP_CSHARP_ROOT_NAMESPACE}};
using Xunit;

namespace {{ANIP_CSHARP_ROOT_NAMESPACE}}.Tests;

public sealed class SupersetDiscoveryEndpointsTests
{
    // "all" is asset_type's declared default, so it is what a call without
    // asset_type carries; it must not filter out every endpoint.
    [Theory]
    [InlineData("all", "dataset,chart,dashboard")]
    [InlineData("", "dataset,chart,dashboard")]
    [InlineData("chart", "chart")]
    // metric and dimension are declared values without a Superset list endpoint.
    [InlineData("metric", "")]
    public void DiscoveryReadsTheCatalogsOfTheAssetType(string assetType, string expected)
    {
        Assert.Equal(expected, string.Join(",", BackendAdapter.DiscoveryEndpoints(assetType).Select(endpoint => endpoint.Kind)));
    }
}
