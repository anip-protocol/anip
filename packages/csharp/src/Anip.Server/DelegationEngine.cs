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
        var concurrent = !string.IsNullOrEmpty(request.ConcurrentBranches)
            ? request.ConcurrentBranches : "allowed";
        var constraints = new DelegationConstraints
        {
            MaxDelegationDepth = 3,
            ConcurrentBranches = concurrent,
            Budget = request.Budget
        };

        // Determine issuer and root_principal.
        var issuer = serviceId;
        var rootPrincipal = principal;
        string? parent = null;

        // v0.23 SPEC §4.8: child tokens inherit parent.session_id verbatim.
        // session_id is settable only at root issuance; child requests must
        // not override it.
        string? sessionId = request.SessionId;

        // If there's a parent token, look it up by ID for sub-delegation.
        if (!string.IsNullOrEmpty(request.ParentToken))
        {
            var parentToken = storage.LoadToken(request.ParentToken);
            if (parentToken == null)
            {
                throw new AnipError(Constants.FailureInvalidToken,
                    $"parent token not found: {request.ParentToken}");
            }

            // Trust boundary: only the holder of a token (its subject) may
            // delegate from it. A token ID is not a credential.
            if (principal != parentToken.Subject)
            {
                throw new AnipError(Constants.FailureInsufficientAuthority,
                    $"Caller '{principal}' is not the parent token's subject ('{parentToken.Subject}') — only the delegatee can sub-delegate");
            }
            // A child token can never carry more scope than its parent.
            ValidateScopeNarrowing(parentToken, request.Scope);

            issuer = parentToken.Subject;
            rootPrincipal = parentToken.RootPrincipal ?? principal;
            parent = parentToken.TokenId;
            constraints = parentToken.Constraints;
            sessionId = parentToken.SessionId;

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
            CallerClass = request.CallerClass,
            SessionId = sessionId
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
            Expires = expires.ToString("o"),
            TaskId = purpose.TaskId
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

    private const string ScopeBudgetMarker = ":max_$";

    /// <summary>Strips a scope's constraint suffix: "travel.book:max_$500" -> "travel.book".</summary>
    private static string ScopeBase(string scope) => scope.Split(':')[0];

    /// <summary>
    /// Returns the "max_$" amount carried by a scope string, or null when it
    /// is absent or not a finite, non-negative number. NaN in particular must
    /// never be accepted: it compares false against everything.
    /// </summary>
    private static double? ScopeBudget(string scope)
    {
        var idx = scope.IndexOf(ScopeBudgetMarker, StringComparison.Ordinal);
        if (idx < 0) return null;
        var raw = scope[(idx + ScopeBudgetMarker.Length)..];
        if (!double.TryParse(raw, System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture, out var value))
        {
            return null;
        }
        if (double.IsNaN(value) || double.IsInfinity(value) || value < 0) return null;
        return value;
    }

    /// <summary>
    /// Rejects a delegated token whose scope is not within its parent's:
    /// every child scope must equal a parent scope or sit below it ("travel"
    /// covers "travel.search"), and a budget carried by the parent scope may
    /// be lowered but not dropped, raised or replaced by a malformed value.
    /// </summary>
    internal static void ValidateScopeNarrowing(DelegationToken parent, List<string>? childScope)
    {
        if (childScope == null) return;
        var parentBases = parent.Scope.Select(ScopeBase).ToList();

        static AnipError Escalation(string detail) =>
            new AnipError(Constants.FailureScopeEscalation, detail).WithResolution("request_new_delegation");

        foreach (var child in childScope)
        {
            var childBase = ScopeBase(child);
            var covered = parentBases.Any(b =>
                childBase == b || childBase.StartsWith(b + ".", StringComparison.Ordinal));
            if (!covered)
            {
                throw Escalation(
                    $"child token scope '{childBase}' is not a subset of parent token scopes: {string.Join(", ", parentBases.OrderBy(b => b, StringComparer.Ordinal))}");
            }

            foreach (var parentScope in parent.Scope)
            {
                if (!parentScope.Contains(ScopeBudgetMarker, StringComparison.Ordinal)
                    || ScopeBase(parentScope) != childBase)
                {
                    continue;
                }
                var parentBudget = ScopeBudget(parentScope)
                    ?? throw Escalation($"parent scope '{childBase}' carries a malformed budget; it cannot be delegated");
                if (!child.Contains(ScopeBudgetMarker, StringComparison.Ordinal))
                {
                    throw Escalation(
                        $"child dropped budget constraint from scope '{childBase}' (parent has max ${parentBudget})");
                }
                var childBudget = ScopeBudget(child)
                    ?? throw Escalation($"child budget for scope '{childBase}' is not a finite, non-negative amount");
                // Written as "not within" so that any unexpected value fails closed.
                if (!(childBudget <= parentBudget))
                {
                    throw Escalation(
                        $"child budget ${childBudget} exceeds parent budget ${parentBudget} for scope '{childBase}'");
                }
            }
        }
    }

    /// <summary>
    /// Enforces purpose binding: a token can only invoke the capability it
    /// was issued for, even when its scope would cover another.
    /// </summary>
    public static void ValidatePurpose(DelegationToken token, string capabilityName)
    {
        if (token.Purpose?.Capability == capabilityName) return;
        throw new AnipError(Constants.FailurePurposeMismatch,
                $"delegation token purpose is {token.Purpose?.Capability} but request is for {capabilityName}")
            .WithResolution("request_new_delegation").WithRetry();
    }

    /// <summary>
    /// Walks the token's delegation chain up to its root and rejects chains
    /// that are incomplete, deeper than the token's max_delegation_depth, or
    /// that pass through an expired ancestor.
    /// </summary>
    public static void ValidateChain(IStorage storage, DelegationToken token)
    {
        var depth = 0;
        var seen = new HashSet<string> { token.TokenId };
        var now = DateTimeOffset.UtcNow;

        var current = token;
        while (!string.IsNullOrEmpty(current.Parent))
        {
            var ancestor = storage.LoadToken(current.Parent);
            if (ancestor == null || !seen.Add(ancestor.TokenId))
            {
                throw new AnipError(Constants.FailureBrokenDelegationChain,
                        $"delegation chain is incomplete — ancestor token '{current.Parent}' is not registered")
                    .WithResolution("request_deeper_delegation").WithRetry();
            }
            if (DateTimeOffset.TryParse(ancestor.Expires, System.Globalization.CultureInfo.InvariantCulture,
                    System.Globalization.DateTimeStyles.AssumeUniversal, out var expires) && expires < now)
            {
                throw new AnipError(Constants.FailureParentTokenExpired,
                        $"ancestor token {ancestor.TokenId} in delegation chain has expired")
                    .WithResolution("refresh_binding").WithRetry();
            }
            current = ancestor;
            depth++;
        }

        var maxDepth = token.Constraints?.MaxDelegationDepth ?? 0;
        if (depth > maxDepth)
        {
            throw new AnipError(Constants.FailureDelegationDepthExceeded,
                    $"delegation chain depth is {depth}, max allowed is {maxDepth}")
                .WithResolution("request_deeper_delegation").WithRetry();
        }
    }

    /// <summary>
    /// Runs every check a token must pass before it may invoke a capability:
    /// scope, purpose binding, and the delegation chain. Token signature and
    /// expiry are verified earlier, by <see cref="ResolveBearerToken"/>.
    /// </summary>
    public static void ValidateDelegation(IStorage storage, DelegationToken token,
        List<string> minimumScope, string capabilityName)
    {
        ValidateScope(token, minimumScope);
        ValidatePurpose(token, capabilityName);
        ValidateChain(storage, token);
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

        // v0.23 SPEC §4.8: enforce session_id consistency between the signed
        // JWT and stored state. This is the trust anchor for session_bound
        // ApprovalGrant continuations. Both sides must agree — a stored
        // session_id without a matching signed claim is just as broken as a
        // signed claim without a stored session_id, since both indicate the
        // token was issued in a different state than what's now being
        // presented.
        var jwtSession = jwtToken.SessionId ?? "";
        var storedSession = stored.SessionId ?? "";
        if (jwtSession != storedSession)
        {
            throw new AnipError(Constants.FailureInvalidToken,
                $"session_id mismatch: jwt={(string.IsNullOrEmpty(jwtSession) ? "<absent>" : jwtSession)} " +
                $"store={(string.IsNullOrEmpty(storedSession) ? "<absent>" : storedSession)}");
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
