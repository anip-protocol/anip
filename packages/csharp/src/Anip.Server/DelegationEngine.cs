using System.Security.Cryptography;
using Anip.Core;
using Anip.Crypto;

namespace Anip.Server;

/// <summary>
/// Delegation engine: token issuance, scope validation, and bearer token resolution.
/// </summary>
public static class DelegationEngine
{
    /// <summary>
    /// Creates a delegation token, signs it as a JWT, and stores it.
    /// </summary>
    public static TokenResponse IssueDelegationToken(
        KeyManager keys,
        IStorage storage,
        string serviceId,
        string principal,
        TokenRequest request)
    {
        var tokenId = GenerateTokenId();
        var now = DateTime.UtcNow;

        var ttlHours = request.TtlHours > 0 ? request.TtlHours : 2;
        var expires = now.AddHours(ttlHours);

        // Build purpose — use caller-supplied task_id if present
        var pp = request.PurposeParameters != null
            ? new Dictionary<string, object>(request.PurposeParameters)
            : new Dictionary<string, object>();
        string? resolvedTaskId;
        if (pp.TryGetValue("task_id", out var callerTaskId) && callerTaskId != null)
        {
            resolvedTaskId = callerTaskId.ToString();
            pp.Remove("task_id");
        }
        else if (request.PurposeParameters == null)
        {
            resolvedTaskId = $"task-{tokenId}";
        }
        else
        {
            resolvedTaskId = null;
        }
        var purpose = new Purpose
        {
            Capability = request.Capability,
            Parameters = pp,
            TaskId = resolvedTaskId
        };

        // Build constraints.
        var constraints = new DelegationConstraints
        {
            MaxDelegationDepth = 3,
            ConcurrentBranches = "allowed",
            Budget = request.Budget
        };

        // Determine issuer and root_principal.
        var issuer = serviceId;
        var rootPrincipal = principal;
        string? parent = null;

        // If there's a parent token, look it up by ID for sub-delegation.
        if (!string.IsNullOrEmpty(request.ParentToken))
        {
            var parentToken = storage.LoadToken(request.ParentToken);
            if (parentToken == null)
            {
                throw new AnipError(Constants.FailureInvalidToken,
                    $"parent token not found: {request.ParentToken}");
            }

            issuer = parentToken.Subject;
            rootPrincipal = parentToken.RootPrincipal ?? principal;
            parent = parentToken.TokenId;
            constraints = parentToken.Constraints;

            // Budget narrowing: child budget must not exceed parent budget.
            if (parentToken.Constraints.Budget != null)
            {
                if (request.Budget == null)
                {
                    // Child inherits parent budget.
                    constraints.Budget = parentToken.Constraints.Budget;
                }
                else if (request.Budget.Currency != parentToken.Constraints.Budget.Currency)
                {
                    throw new AnipError(Constants.FailureBudgetCurrencyMismatch,
                        $"Child budget currency {request.Budget.Currency} does not match parent {parentToken.Constraints.Budget.Currency}");
                }
                else if (request.Budget.MaxAmount > parentToken.Constraints.Budget.MaxAmount)
                {
                    throw new AnipError(Constants.FailureBudgetExceeded,
                        $"Child budget ${request.Budget.MaxAmount} exceeds parent budget ${parentToken.Constraints.Budget.MaxAmount}");
                }
                else
                {
                    constraints.Budget = request.Budget;
                }
            }
            else if (request.Budget != null)
            {
                constraints.Budget = request.Budget;
            }
        }

        // Default subject to the authenticated principal if not provided.
        var subject = string.IsNullOrEmpty(request.Subject) ? principal : request.Subject;

        // Build the token record.
        var token = new DelegationToken
        {
            TokenId = tokenId,
            Issuer = issuer,
            Subject = subject,
            Scope = request.Scope,
            Purpose = purpose,
            Parent = parent,
            Expires = expires.ToString("o"),
            Constraints = constraints,
            RootPrincipal = rootPrincipal,
            CallerClass = request.CallerClass
        };

        // Store the token.
        storage.StoreToken(token);

        // Sign as JWT.
        var jwt = JwtSigner.SignToken(keys.GetSigningKey(), keys.GetSigningKid(), token, serviceId);

        return new TokenResponse
        {
            Issued = true,
            TokenId = tokenId,
            Token = jwt,
            Expires = expires.ToString("o")
        };
    }

    /// <summary>
    /// Validates that the token's scope covers the required minimum scope.
    /// Uses prefix matching: a token scope "data" covers required scope "data.read".
    /// Throws AnipError if scope is insufficient.
    /// </summary>
    public static void ValidateScope(DelegationToken token, List<string> requiredScope)
    {
        var tokenScopeBases = token.Scope
            .Select(s => s.Split(':')[0])
            .ToList();

        var missing = new List<string>();

        foreach (var required in requiredScope)
        {
            var matched = tokenScopeBases.Any(b =>
                b == required || required.StartsWith(b + "."));
            if (!matched)
            {
                missing.Add(required);
            }
        }

        if (missing.Count > 0)
        {
            throw new AnipError(
                Constants.FailureScopeInsufficient,
                $"delegation chain lacks scope(s): {string.Join(", ", missing)}"
            ).WithResolution("request_broader_scope");
        }
    }

    /// <summary>
    /// Verifies a JWT, loads the stored token, and compares signed claims
    /// against stored state to prevent forged inline fields.
    /// </summary>
    public static DelegationToken ResolveBearerToken(
        KeyManager keys,
        IStorage storage,
        string serviceId,
        string jwt)
    {
        // 1. Verify JWT signature + expiry + issuer.
        DelegationToken jwtToken;
        try
        {
            jwtToken = JwtVerifier.VerifyAndExtract(jwt, keys.GetSigningKey(), serviceId);
        }
        catch (AnipError e) when (e.ErrorType == Constants.FailureTokenExpired)
        {
            throw new AnipError(Constants.FailureTokenExpired, "delegation token has expired");
        }
        catch (AnipError)
        {
            throw;
        }
        catch (Exception ex)
        {
            throw new AnipError(Constants.FailureInvalidToken,
                "JWT verification failed: " + ex.Message);
        }

        // 2. Extract token_id.
        if (string.IsNullOrEmpty(jwtToken.TokenId))
        {
            throw new AnipError(Constants.FailureInvalidToken, "JWT missing jti claim");
        }

        // 3. Load stored token.
        var stored = storage.LoadToken(jwtToken.TokenId);
        if (stored == null)
        {
            throw new AnipError(Constants.FailureInvalidToken, "token not found in storage");
        }

        // 4. Compare signed claims against stored state.
        if (!string.IsNullOrEmpty(jwtToken.Subject) && jwtToken.Subject != stored.Subject)
        {
            throw new AnipError(Constants.FailureInvalidToken,
                "subject mismatch between JWT and stored token");
        }

        if (!string.IsNullOrEmpty(jwtToken.RootPrincipal) && jwtToken.RootPrincipal != stored.RootPrincipal)
        {
            throw new AnipError(Constants.FailureInvalidToken,
                "root_principal mismatch between JWT and stored token");
        }

        // 5. Return stored token.
        return stored;
    }

    private static string GenerateTokenId()
    {
        var bytes = new byte[6];
        RandomNumberGenerator.Fill(bytes);
        return $"anip-{Convert.ToHexString(bytes).ToLowerInvariant()}";
    }
}
