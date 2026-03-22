using Anip.Core;
using Anip.Service;

namespace Anip.Mcp;

/// <summary>
/// Auth bridge for the MCP HTTP interface.
/// JWT-first, API-key-fallback. Subject "adapter:anip-mcp".
/// </summary>
public static class McpAuthBridge
{
    /// <summary>
    /// Resolves auth from a bearer token for MCP HTTP transport.
    /// Tries JWT resolution first; falls back to API key authentication
    /// and issues a synthetic delegation token with subject "adapter:anip-mcp".
    /// </summary>
    public static DelegationToken ResolveAuth(string bearer, AnipService service, string capabilityName)
    {
        // Try as JWT first.
        AnipError? jwtError;
        try
        {
            return service.ResolveBearerToken(bearer);
        }
        catch (AnipError e)
        {
            jwtError = e;
        }

        // Try as API key.
        var principal = service.AuthenticateBearer(bearer);
        if (!string.IsNullOrEmpty(principal))
        {
            var capDecl = service.GetCapabilityDeclaration(capabilityName);
            var minScope = capDecl?.MinimumScope;
            if (minScope == null || minScope.Count == 0)
            {
                minScope = new List<string> { "*" };
            }

            var req = new TokenRequest
            {
                Subject = "adapter:anip-mcp",
                Scope = minScope,
                Capability = capabilityName,
                PurposeParameters = new Dictionary<string, object> { ["source"] = "mcp" },
            };

            var tokenResp = service.IssueToken(principal, req);
            return service.ResolveBearerToken(tokenResp.Token);
        }

        throw jwtError;
    }
}
