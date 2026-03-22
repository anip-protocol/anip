namespace Anip.AspNetCore;

/// <summary>
/// Configuration options for the ANIP ASP.NET Core integration.
/// </summary>
public class AnipOptions
{
    /// <summary>
    /// Whether the GET /-/health endpoint is enabled. Default: true.
    /// </summary>
    public bool HealthEndpoint { get; set; } = true;
}
