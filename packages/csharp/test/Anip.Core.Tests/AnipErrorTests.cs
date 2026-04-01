namespace Anip.Core.Tests;

public class AnipErrorTests
{
    [Fact]
    public void Constructor_SetsProperties()
    {
        var resolution = new Resolution
        {
            Action = "request_new_delegation",
            RecoveryClass = Constants.RecoveryClassForAction("request_new_delegation"),
            Requires = "oauth2",
            GrantableBy = "admin"
        };

        var error = new AnipError(
            Constants.FailureAuthRequired,
            "Token has expired",
            resolution,
            retry: true);

        Assert.Equal(Constants.FailureAuthRequired, error.ErrorType);
        Assert.Equal("Token has expired", error.Detail);
        Assert.NotNull(error.Resolution);
        Assert.Equal("request_new_delegation", error.Resolution!.Action);
        Assert.Equal("oauth2", error.Resolution.Requires);
        Assert.Equal("admin", error.Resolution.GrantableBy);
        Assert.True(error.Retry);
    }

    [Fact]
    public void Constructor_DefaultValues()
    {
        var error = new AnipError(Constants.FailureNotFound, "Resource not found");

        Assert.Equal(Constants.FailureNotFound, error.ErrorType);
        Assert.Equal("Resource not found", error.Detail);
        Assert.Null(error.Resolution);
        Assert.False(error.Retry);
    }

    [Fact]
    public void ExtendsException()
    {
        var error = new AnipError(Constants.FailureInternalError, "Something broke");

        Assert.IsAssignableFrom<Exception>(error);
        Assert.Equal("Something broke", error.Message);
    }

    [Fact]
    public void WithResolution_SetsResolution()
    {
        var error = new AnipError(Constants.FailureAuthRequired, "Need auth")
            .WithResolution("provide_credentials");

        Assert.NotNull(error.Resolution);
        Assert.Equal("provide_credentials", error.Resolution!.Action);
        Assert.Equal("retry_now", error.Resolution.RecoveryClass);
    }

    [Fact]
    public void WithRetry_SetsRetryTrue()
    {
        var error = new AnipError(Constants.FailureUnavailable, "Try again")
            .WithRetry();

        Assert.True(error.Retry);
    }

    [Fact]
    public void CanBeCaughtAsException()
    {
        AnipError? caught = null;

        try
        {
            throw new AnipError(Constants.FailureInternalError, "boom");
        }
        catch (Exception ex) when (ex is AnipError anipErr)
        {
            caught = anipErr;
        }

        Assert.NotNull(caught);
        Assert.Equal(Constants.FailureInternalError, caught!.ErrorType);
    }

    [Fact]
    public void Resolution_EstimatedAvailability()
    {
        var resolution = new Resolution
        {
            Action = "wait",
            EstimatedAvailability = "2026-01-01T00:00:00Z"
        };

        Assert.Equal("wait", resolution.Action);
        Assert.Equal("2026-01-01T00:00:00Z", resolution.EstimatedAvailability);
        Assert.Null(resolution.Requires);
        Assert.Null(resolution.GrantableBy);
    }
}
