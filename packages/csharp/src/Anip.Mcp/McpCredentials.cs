namespace Anip.Mcp;

/// <summary>
/// Mount-time credentials for stdio MCP transport.
/// Since stdio has no per-request auth, credentials are provided once at mount time.
/// </summary>
public class McpCredentials
{
    public string? ApiKey { get; set; }
    public List<string>? Scope { get; set; }
    public string? Subject { get; set; }
}
