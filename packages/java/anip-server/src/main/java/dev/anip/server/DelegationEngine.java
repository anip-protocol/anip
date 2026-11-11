package dev.anip.server;

import dev.anip.core.ANIPError;
import dev.anip.core.Budget;
import dev.anip.core.Constants;
import dev.anip.core.DelegationConstraints;
import dev.anip.core.DelegationToken;
import dev.anip.core.Purpose;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.crypto.JwtSigner;
import dev.anip.crypto.JwtVerifier;
import dev.anip.crypto.KeyManager;

import java.security.SecureRandom;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Handles delegation token issuance, resolution, and scope validation.
 */
public final class DelegationEngine {

    private static final SecureRandom RANDOM = new SecureRandom();

    private DelegationEngine() {}

    /**
     * Creates a delegation token, signs it as a JWT, and stores it.
     *
     * @param km        the key manager for signing
     * @param storage   the storage backend
     * @param serviceId the service identifier (issuer and audience)
     * @param principal the authenticated principal making the request
     * @param req       the token request
     * @return the token response containing the signed JWT
     */
    public static TokenResponse issueDelegationToken(
            KeyManager km, Storage storage, String serviceId,
            String principal, TokenRequest req) throws Exception {

        String tokenId = generateTokenId();
        Instant now = Instant.now();

        int ttlHours = req.getTtlHours();
        if (ttlHours <= 0) {
            ttlHours = 2;
        }
        Instant expires = now.plusSeconds((long) ttlHours * 3600);

        // Build purpose — use caller-supplied task_id if present
        Map<String, Object> purposeParams = req.getPurposeParameters() != null
                ? new java.util.HashMap<>(req.getPurposeParameters()) : new java.util.HashMap<>();
        String resolvedTaskId;
        if (purposeParams.containsKey("task_id") && purposeParams.get("task_id") != null) {
            resolvedTaskId = purposeParams.remove("task_id").toString();
        } else if (req.getPurposeParameters() == null) {
            resolvedTaskId = "task-" + tokenId;
        } else {
            resolvedTaskId = null;
        }
        Purpose purpose = new Purpose(
                req.getCapability(),
                purposeParams,
                resolvedTaskId
        );

        // Build constraints.
        String concurrent = req.getConcurrentBranches() != null
                ? req.getConcurrentBranches() : "allowed";
        DelegationConstraints constraints = new DelegationConstraints(3, concurrent,
                req.getBudget());

        // Determine issuer and root_principal.
        String issuer = serviceId;
        String rootPrincipal = principal;
        String parent = "";
        // v0.23: child tokens inherit parent.session_id verbatim. Only honored
        // at root issuance from req.sessionId.
        String sessionId = req.getSessionId();

        // If there's a parent token, look it up by ID for sub-delegation.
        if (req.getParentToken() != null && !req.getParentToken().isEmpty()) {
            DelegationToken parentToken = storage.loadToken(req.getParentToken());
            if (parentToken == null) {
                throw new ANIPError(Constants.FAILURE_INVALID_TOKEN,
                        "parent token not found: " + req.getParentToken());
            }

            // Trust boundary: only the holder of a token (its subject) may
            // delegate from it. A token ID is not a credential.
            if (principal == null || !principal.equals(parentToken.getSubject())) {
                throw new ANIPError(Constants.FAILURE_INSUFFICIENT_AUTHORITY,
                        "Caller '" + principal + "' is not the parent token's subject ('"
                                + parentToken.getSubject() + "') — only the delegatee can sub-delegate");
            }
            // A child token can never carry more scope than its parent.
            validateScopeNarrowing(parentToken, req.getScope());

            issuer = parentToken.getSubject();
            rootPrincipal = parentToken.getRootPrincipal();
            parent = parentToken.getTokenId();
            constraints = parentToken.getConstraints();
            // SPEC.md §4.8: child tokens inherit the parent's session_id verbatim.
            sessionId = parentToken.getSessionId();

            // Budget narrowing: child budget must not exceed parent budget.
            if (parentToken.getConstraints().getBudget() != null) {
                if (req.getBudget() == null) {
                    // Child inherits parent budget.
                    constraints = new DelegationConstraints(
                            constraints.getMaxDelegationDepth(),
                            constraints.getConcurrentBranches(),
                            parentToken.getConstraints().getBudget());
                } else if (!req.getBudget().getCurrency().equals(
                        parentToken.getConstraints().getBudget().getCurrency())) {
                    throw new ANIPError(Constants.FAILURE_BUDGET_CURRENCY_MISMATCH,
                            "Child budget currency " + req.getBudget().getCurrency()
                                    + " does not match parent " + parentToken.getConstraints().getBudget().getCurrency());
                } else if (req.getBudget().getMaxAmount() > parentToken.getConstraints().getBudget().getMaxAmount()) {
                    throw new ANIPError(Constants.FAILURE_BUDGET_EXCEEDED,
                            "Child budget $" + req.getBudget().getMaxAmount()
                                    + " exceeds parent budget $" + parentToken.getConstraints().getBudget().getMaxAmount());
                } else {
                    constraints = new DelegationConstraints(
                            constraints.getMaxDelegationDepth(),
                            constraints.getConcurrentBranches(),
                            req.getBudget());
                }
            } else if (req.getBudget() != null) {
                constraints = new DelegationConstraints(
                        constraints.getMaxDelegationDepth(),
                        constraints.getConcurrentBranches(),
                        req.getBudget());
            }
        }

        // Default subject to the authenticated principal if not provided.
        String subject = req.getSubject();
        if (subject == null || subject.isEmpty()) {
            subject = principal;
        }

        String expiresStr = DateTimeFormatter.ISO_INSTANT.format(expires);

        // Build the token record.
        DelegationToken token = new DelegationToken(
                tokenId, issuer, subject, req.getScope(), purpose,
                parent, expiresStr, constraints, rootPrincipal, req.getCallerClass(),
                sessionId
        );

        // Store the token.
        storage.storeToken(token);

        // Sign as JWT.
        Map<String, Object> claims = new HashMap<>();
        claims.put("jti", tokenId);
        claims.put("iss", serviceId);
        claims.put("sub", subject);
        claims.put("aud", serviceId);
        claims.put("iat", now.getEpochSecond());
        claims.put("exp", expires.getEpochSecond());
        claims.put("scope", req.getScope());
        claims.put("root_principal", rootPrincipal);
        claims.put("capability", req.getCapability());
        claims.put("purpose", JsonHelper.toMap(purpose));
        claims.put("constraints", JsonHelper.toMap(constraints));
        if (!parent.isEmpty()) {
            claims.put("parent_token_id", parent);
        }
        // v0.23: bind session_id into the JWT so resolveBearerToken can verify
        // both sides agree (SPEC.md §4.8 trust model).
        if (sessionId != null && !sessionId.isEmpty()) {
            claims.put("anip:session_id", sessionId);
        }

        String jwt = JwtSigner.signDelegationJwt(km, claims);

        return new TokenResponse(true, tokenId, jwt, expiresStr, purpose.getTaskId());
    }

    /**
     * Verifies a JWT, loads the stored token, and compares signed claims
     * against stored state to prevent forged inline fields.
     *
     * @param km        the key manager for verification
     * @param storage   the storage backend
     * @param serviceId the service identifier (issuer and audience)
     * @param jwtStr    the compact serialized JWT string
     * @return the stored delegation token
     */
    public static DelegationToken resolveBearerToken(
            KeyManager km, Storage storage, String serviceId, String jwtStr) throws Exception {

        // 1. Verify JWT signature + expiry + issuer/audience.
        Map<String, Object> claims;
        try {
            claims = JwtVerifier.verifyDelegationJwt(km, jwtStr, serviceId, serviceId);
        } catch (SecurityException e) {
            String msg = e.getMessage();
            if (msg != null && msg.contains("expired")) {
                throw new ANIPError(Constants.FAILURE_TOKEN_EXPIRED,
                        "delegation token has expired");
            }
            throw new ANIPError(Constants.FAILURE_INVALID_TOKEN,
                    "JWT verification failed: " + msg);
        } catch (Exception e) {
            throw new ANIPError(Constants.FAILURE_INVALID_TOKEN,
                    "JWT verification failed: " + e.getMessage());
        }

        // 2. Extract jti -> token_id.
        Object jtiObj = claims.get("jti");
        String tokenId = jtiObj instanceof String s ? s : null;
        if (tokenId == null || tokenId.isEmpty()) {
            throw new ANIPError(Constants.FAILURE_INVALID_TOKEN, "JWT missing jti claim");
        }

        // 3. Load stored token.
        DelegationToken stored;
        try {
            stored = storage.loadToken(tokenId);
        } catch (Exception e) {
            throw new ANIPError(Constants.FAILURE_INTERNAL_ERROR,
                    "error loading token: " + e.getMessage());
        }
        if (stored == null) {
            throw new ANIPError(Constants.FAILURE_INVALID_TOKEN, "token not found in storage");
        }

        // 4. Compare signed claims against stored state.
        Object subObj = claims.get("sub");
        if (subObj instanceof String sub && !sub.equals(stored.getSubject())) {
            throw new ANIPError(Constants.FAILURE_INVALID_TOKEN,
                    "subject mismatch between JWT and stored token");
        }

        Object rpObj = claims.get("root_principal");
        if (rpObj instanceof String rp && !rp.equals(stored.getRootPrincipal())) {
            throw new ANIPError(Constants.FAILURE_INVALID_TOKEN,
                    "root_principal mismatch between JWT and stored token");
        }

        // v0.23: if either side carries a session_id, both MUST agree.
        // SPEC.md §4.8: session_id MUST come from the signed token, not from
        // caller-supplied input.
        Object sidObj = claims.get("anip:session_id");
        String jwtSessionId = sidObj instanceof String s ? s : null;
        String storedSessionId = stored.getSessionId();
        boolean jwtPresent = jwtSessionId != null && !jwtSessionId.isEmpty();
        boolean storedPresent = storedSessionId != null && !storedSessionId.isEmpty();
        if (jwtPresent != storedPresent
                || (jwtPresent && !jwtSessionId.equals(storedSessionId))) {
            throw new ANIPError(Constants.FAILURE_INVALID_TOKEN,
                    "session_id mismatch between JWT and stored token");
        }

        // 5. Return stored token.
        return stored;
    }

    /**
     * Checks if the token's scope covers the capability's minimum_scope.
     * Throws ANIPError with scope_insufficient if insufficient.
     *
     * @param token        the delegation token to validate
     * @param minimumScope the required scope strings
     */
    public static void validateScope(DelegationToken token, List<String> minimumScope) {
        if (minimumScope == null || minimumScope.isEmpty()) {
            return;
        }

        // Extract base scopes from token (before ':' modifier).
        List<String> tokenScopeBases = token.getScope().stream()
                .map(s -> s.split(":")[0])
                .toList();

        List<String> missing = minimumScope.stream()
                .filter(required -> tokenScopeBases.stream().noneMatch(
                        base -> base.equals(required) || required.startsWith(base + ".")))
                .toList();

        if (!missing.isEmpty()) {
            throw new ANIPError(
                    Constants.FAILURE_SCOPE_INSUFFICIENT,
                    "delegation chain lacks scope(s): " + String.join(", ", missing)
            ).withResolution("request_broader_scope");
        }
    }

    /** Strips a scope's constraint suffix: "travel.book:max_$500" -> "travel.book". */
    private static String scopeBase(String scope) {
        return scope.split(":")[0];
    }

    /**
     * Whether a held scope base covers a needed one: "travel" covers "travel"
     * and "travel.search", not "travelogue".
     */
    private static boolean scopeCovers(String heldBase, String neededBase) {
        return neededBase.equals(heldBase) || neededBase.startsWith(heldBase + ".");
    }

    /** Result of {@link #narrowedScope}. */
    public record NarrowedScope(List<String> scope, List<String> missing) {}

    /**
     * Returns the scope a token derived from {@code heldScope} should carry to
     * cover {@code required}, and the required scopes it does not cover. Each
     * entry keeps the constraint suffix of the held scope that covers it:
     * holding "travel:max_$500" gives "travel.book:max_$500" for a required
     * "travel.book".
     */
    public static NarrowedScope narrowedScope(List<String> heldScope, List<String> required) {
        List<String> narrowed = new java.util.ArrayList<>();
        List<String> missing = new java.util.ArrayList<>();
        if (required != null) {
            for (String needed : required) {
                String match = null;
                for (String held : heldScope) {
                    String base = scopeBase(held);
                    if (scopeCovers(base, needed)) {
                        match = needed + held.substring(base.length());
                        break;
                    }
                }
                if (match == null) {
                    missing.add(needed);
                } else {
                    narrowed.add(match);
                }
            }
        }
        return new NarrowedScope(narrowed, missing);
    }

    /** Whether a scope string carries a "max_$" budget at all. */
    private static boolean hasScopeBudget(String scope) {
        return scope.contains(":max_$");
    }

    /**
     * Returns the "max_$" amount carried by a scope string, or null when it is
     * absent or not a finite, non-negative number. NaN in particular must
     * never be accepted: it compares false against everything.
     */
    private static Double scopeBudget(String scope) {
        int idx = scope.indexOf(":max_$");
        if (idx < 0) {
            return null;
        }
        try {
            double value = Double.parseDouble(scope.substring(idx + ":max_$".length()));
            if (Double.isNaN(value) || Double.isInfinite(value) || value < 0) {
                return null;
            }
            return value;
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /**
     * Rejects a delegated token whose scope is not within its parent's: every
     * child scope must equal a parent scope or sit below it ("travel" covers
     * "travel.search"), and a budget carried by the parent scope may be
     * lowered but not dropped or raised.
     */
    static void validateScopeNarrowing(DelegationToken parent, List<String> childScope) {
        if (childScope == null) {
            return;
        }
        List<String> parentBases = parent.getScope().stream().map(DelegationEngine::scopeBase).toList();

        for (String child : childScope) {
            String childBase = scopeBase(child);
            boolean covered = parentBases.stream().anyMatch(base -> scopeCovers(base, childBase));
            if (!covered) {
                throw scopeEscalation("child token scope '" + childBase
                        + "' is not a subset of parent token scopes: "
                        + String.join(", ", parentBases.stream().sorted().toList()));
            }

            for (String parentScope : parent.getScope()) {
                // A budget on a parent scope applies to every scope beneath
                // it: "travel:max_$500" also bounds "travel.book".
                if (!hasScopeBudget(parentScope) || !scopeCovers(scopeBase(parentScope), childBase)) {
                    continue;
                }
                Double parentBudget = scopeBudget(parentScope);
                if (parentBudget == null) {
                    throw scopeEscalation("parent scope '" + childBase
                            + "' carries a malformed budget; it cannot be delegated");
                }
                if (!hasScopeBudget(child)) {
                    throw scopeEscalation("child dropped budget constraint from scope '" + childBase
                            + "' (parent has max $" + parentBudget + ")");
                }
                Double childBudget = scopeBudget(child);
                if (childBudget == null) {
                    throw scopeEscalation("child budget for scope '" + childBase
                            + "' is not a finite, non-negative amount");
                }
                // Written as "not within" so that any unexpected value fails closed.
                if (!(childBudget <= parentBudget)) {
                    throw scopeEscalation("child budget $" + childBudget + " exceeds parent budget $"
                            + parentBudget + " for scope '" + childBase + "'");
                }
            }
        }
    }

    private static ANIPError scopeEscalation(String detail) {
        return new ANIPError(Constants.FAILURE_SCOPE_ESCALATION, detail)
                .withResolution("request_new_delegation");
    }

    /**
     * Enforces purpose binding: a token can only invoke the capability it was
     * issued for, even when its scope would cover another.
     */
    public static void validatePurpose(DelegationToken token, String capabilityName) {
        String bound = token.getPurpose() != null ? token.getPurpose().getCapability() : null;
        if (capabilityName.equals(bound)) {
            return;
        }
        throw new ANIPError(Constants.FAILURE_PURPOSE_MISMATCH,
                "delegation token purpose is " + bound + " but request is for " + capabilityName)
                .withResolution("request_new_delegation").withRetry();
    }

    /**
     * Walks the token's delegation chain up to its root and rejects chains
     * that are incomplete, deeper than the token's max_delegation_depth, or
     * that pass through an expired ancestor.
     */
    public static void validateChain(Storage storage, DelegationToken token) {
        int depth = 0;
        java.util.Set<String> seen = new java.util.HashSet<>();
        seen.add(token.getTokenId());
        Instant now = Instant.now();

        DelegationToken current = token;
        while (current.getParent() != null && !current.getParent().isEmpty()) {
            DelegationToken ancestor;
            try {
                ancestor = storage.loadToken(current.getParent());
            } catch (ANIPError e) {
                throw e;
            } catch (Exception e) {
                throw new ANIPError(Constants.FAILURE_INTERNAL_ERROR, "error loading token: " + e.getMessage());
            }
            if (ancestor == null || !seen.add(ancestor.getTokenId())) {
                throw new ANIPError(Constants.FAILURE_BROKEN_DELEGATION_CHAIN,
                        "delegation chain is incomplete — ancestor token '" + current.getParent()
                                + "' is not registered")
                        .withResolution("request_deeper_delegation").withRetry();
            }
            Instant expires = parseInstant(ancestor.getExpires());
            if (expires != null && expires.isBefore(now)) {
                throw new ANIPError(Constants.FAILURE_PARENT_TOKEN_EXPIRED,
                        "ancestor token " + ancestor.getTokenId() + " in delegation chain has expired")
                        .withResolution("refresh_binding").withRetry();
            }
            current = ancestor;
            depth++;
        }

        int maxDepth = token.getConstraints() != null ? token.getConstraints().getMaxDelegationDepth() : 0;
        if (depth > maxDepth) {
            throw new ANIPError(Constants.FAILURE_DELEGATION_DEPTH_EXCEEDED,
                    "delegation chain depth is " + depth + ", max allowed is " + maxDepth)
                    .withResolution("request_deeper_delegation").withRetry();
        }
    }

    private static Instant parseInstant(String value) {
        if (value == null || value.isEmpty()) {
            return null;
        }
        try {
            return Instant.parse(value);
        } catch (java.time.format.DateTimeParseException e) {
            return null;
        }
    }

    /**
     * Runs every check a token must pass before it may invoke a capability:
     * scope, purpose binding, and the delegation chain. Token signature and
     * expiry are verified earlier, by {@link #resolveBearerToken}.
     */
    public static void validateDelegation(Storage storage, DelegationToken token,
                                          List<String> minimumScope, String capabilityName) {
        validateScope(token, minimumScope);
        validatePurpose(token, capabilityName);
        validateChain(storage, token);
    }

    /**
     * Generates a random token ID in the format "anip-{12 hex chars}".
     */
    private static String generateTokenId() {
        byte[] b = new byte[6];
        RANDOM.nextBytes(b);
        StringBuilder sb = new StringBuilder("anip-");
        for (byte v : b) {
            sb.append(String.format("%02x", v & 0xff));
        }
        return sb.toString();
    }
}
