using Anip.Service;

namespace Anip.Service.Tests;

public class EventClassificationTests
{
    [Fact]
    public void HighRiskSuccess_WriteAndSuccess()
    {
        Assert.Equal("high_risk_success", EventClassification.Classify("write", true, null));
    }

    [Fact]
    public void HighRiskSuccess_Irreversible()
    {
        Assert.Equal("high_risk_success", EventClassification.Classify("irreversible", true, null));
    }

    [Fact]
    public void HighRiskSuccess_Transactional()
    {
        Assert.Equal("high_risk_success", EventClassification.Classify("transactional", true, null));
    }

    [Fact]
    public void LowRiskSuccess_ReadAndSuccess()
    {
        Assert.Equal("low_risk_success", EventClassification.Classify("read", true, null));
    }

    [Fact]
    public void LowRiskSuccess_NoneAndSuccess()
    {
        Assert.Equal("low_risk_success", EventClassification.Classify("none", true, null));
    }

    [Fact]
    public void MalformedOrSpam_EmptySideEffect()
    {
        Assert.Equal("malformed_or_spam", EventClassification.Classify("", false, "unknown_capability"));
    }

    [Fact]
    public void MalformedOrSpam_NullSideEffect()
    {
        Assert.Equal("malformed_or_spam", EventClassification.Classify(null, false, "unknown_capability"));
    }

    [Fact]
    public void MalformedOrSpam_UnknownCapabilityFailure()
    {
        Assert.Equal("malformed_or_spam", EventClassification.Classify("read", false, "unknown_capability"));
    }

    [Fact]
    public void MalformedOrSpam_StreamingNotSupported()
    {
        Assert.Equal("malformed_or_spam", EventClassification.Classify("read", false, "streaming_not_supported"));
    }

    [Fact]
    public void MalformedOrSpam_InternalError()
    {
        Assert.Equal("malformed_or_spam", EventClassification.Classify("write", false, "internal_error"));
    }

    [Fact]
    public void HighRiskDenial_ScopeInsufficient()
    {
        Assert.Equal("high_risk_denial", EventClassification.Classify("write", false, "scope_insufficient"));
    }

    [Fact]
    public void HighRiskDenial_InvalidToken()
    {
        Assert.Equal("high_risk_denial", EventClassification.Classify("read", false, "invalid_token"));
    }

    [Fact]
    public void MalformedOrSpam_SuccessWithEmptySideEffect()
    {
        Assert.Equal("malformed_or_spam", EventClassification.Classify("", true, null));
    }
}
