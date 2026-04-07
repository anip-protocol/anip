namespace Anip.Core.Tests;

public class ConstantsTests
{
    [Fact]
    public void GenerateInvocationId_HasCorrectFormat()
    {
        var id = Constants.GenerateInvocationId();

        Assert.StartsWith("inv-", id);
        Assert.Equal(16, id.Length); // "inv-" (4) + 12 hex chars
    }

    [Fact]
    public void GenerateInvocationId_IsUnique()
    {
        var id1 = Constants.GenerateInvocationId();
        var id2 = Constants.GenerateInvocationId();

        Assert.NotEqual(id1, id2);
    }

    [Fact]
    public void GenerateInvocationId_ContainsOnlyHexCharsAfterPrefix()
    {
        var id = Constants.GenerateInvocationId();
        var hexPart = id[4..];

        Assert.All(hexPart, c => Assert.True(
            (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'),
            $"Character '{c}' is not a lowercase hex character"));
    }

    [Theory]
    [InlineData(Constants.FailureAuthRequired, 401)]
    [InlineData(Constants.FailureInvalidToken, 401)]
    [InlineData(Constants.FailureTokenExpired, 401)]
    [InlineData(Constants.FailureScopeInsufficient, 403)]
    [InlineData(Constants.FailureBudgetExceeded, 403)]
    [InlineData(Constants.FailurePurposeMismatch, 403)]
    [InlineData(Constants.FailureUnknownCapability, 404)]
    [InlineData(Constants.FailureNotFound, 404)]
    [InlineData(Constants.FailureUnavailable, 409)]
    [InlineData(Constants.FailureConcurrentLock, 409)]
    [InlineData(Constants.FailureInternalError, 500)]
    [InlineData(Constants.FailureInvalidParameters, 400)]
    public void FailureStatusCode_MapsCorrectly(string failureType, int expectedStatus)
    {
        Assert.Equal(expectedStatus, Constants.FailureStatusCode(failureType));
    }

    [Fact]
    public void FailureStatusCode_UnknownType_Returns400()
    {
        Assert.Equal(400, Constants.FailureStatusCode("some_unknown_type"));
    }

    [Fact]
    public void FailureStatusCode_Null_Returns400()
    {
        Assert.Equal(400, Constants.FailureStatusCode(null));
    }

    [Fact]
    public void ProtocolVersion_IsCorrect()
    {
        // Intentionally hardcoded — this is the one place that verifies the constant value.
        // Update this when bumping the protocol version.
        Assert.Equal("anip/0.22", Constants.ProtocolVersion);
    }

    [Fact]
    public void ManifestVersion_IsCorrect()
    {
        Assert.Equal("0.10.0", Constants.ManifestVersion);
    }

    [Fact]
    public void DefaultProfile_ContainsExpectedKeys()
    {
        Assert.Equal("1.0", Constants.DefaultProfile["core"]);
        Assert.Equal("1.0", Constants.DefaultProfile["cost"]);
        Assert.Equal("1.0", Constants.DefaultProfile["capability_graph"]);
        Assert.Equal("1.0", Constants.DefaultProfile["state_session"]);
        Assert.Equal("1.0", Constants.DefaultProfile["observability"]);
        Assert.Equal(5, Constants.DefaultProfile.Count);
    }

    [Fact]
    public void MerkleHashPrefixes_AreCorrect()
    {
        Assert.Equal(0x00, Constants.LeafHashPrefix);
        Assert.Equal(0x01, Constants.NodeHashPrefix);
    }
}
