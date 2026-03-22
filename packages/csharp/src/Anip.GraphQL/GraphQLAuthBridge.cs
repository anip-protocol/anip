using Anip.Core;
using Anip.Service;

namespace Anip.GraphQL;

/// <summary>
/// Per-field auth resolution for the GraphQL interface.
/// JWT-first, API-key-fallback. Subject "adapter:anip-graphql".
/// Auth errors in result body, not HTTP errors.
/// </summary>
public static class GraphQLAuthBridge
{
    /// <summary>
    /// Resolves auth from a bearer token for a GraphQL field.
    /// Same pattern as REST auth bridge but with graphql subject and source.
    /// </summary>
    public static DelegationToken ResolveAuth(string bearer, AnipService service,
                                               string capabilityName)
    {
        // Try as JWT first.
        AnipError jwtError;
        try
        {
            return service.ResolveBearerToken(bearer);
        }
        catch (AnipError e)
        {
            jwtError = e;
        }
        // Only AnipError is caught; any other exception propagates.

        // Try as API key.
        var principal = service.AuthenticateBearer(bearer);
        if (!string.IsNullOrEmpty(principal))
        {
            var capDecl = service.GetCapabilityDeclaration(capabilityName);
            List<string>? minScope = null;
            if (capDecl != null)
            {
                minScope = capDecl.MinimumScope;
            }
            if (minScope == null || minScope.Count == 0)
            {
                minScope = new List<string> { "*" };
            }

            var req = new TokenRequest
            {
                Subject = "adapter:anip-graphql",
                Scope = minScope,
                Capability = capabilityName,
                PurposeParameters = new Dictionary<string, object> { ["source"] = "graphql" },
            };

            TokenResponse tokenResp;
            try
            {
                tokenResp = service.IssueToken(principal, req);
            }
            catch
            {
                // Return the real issuance error, not the stale JWT error.
                throw;
            }

            return service.ResolveBearerToken(tokenResp.Token);
        }

        // Neither JWT nor API key -- surface the original JWT error.
        throw jwtError;
    }
}
