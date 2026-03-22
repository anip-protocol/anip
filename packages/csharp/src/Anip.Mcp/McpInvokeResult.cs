namespace Anip.Mcp;

/// <summary>
/// Result of translating an ANIP invoke response to MCP text format.
/// </summary>
public record McpInvokeResult(string Text, bool IsError);
