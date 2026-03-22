using Anip.Core;
using Anip.Service;

namespace Anip.Rest;

/// <summary>
/// Shared auth bridge for the REST interface.
/// JWT-first, API-key-fallback. Only catches AnipError from JWT resolution.
/// </summary>
public static class RestAuthBridge
{
    /// <summary>
    /// Resolves auth from a bearer token.
    ///
    /// 1. Try service.ResolveBearerToken(bearer) -- JWT mode
    /// 2. If AnipError -- try service.AuthenticateBearer(bearer) -- API key mode
    /// 3. If API key works -- issue synthetic token
    /// 4. If token issuance fails -- return the real issuance error
    /// 5. If neither -- re-throw original JWT error
    /// 6. Only catch AnipError from JWT, rethrow unexpected exceptions
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
            // Issue synthetic token.
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
                Subject = "adapter:anip-rest",
                Scope = minScope,
                Capability = capabilityName,
                PurposeParameters = new Dictionary<string, object> { ["source"] = "rest" },
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
