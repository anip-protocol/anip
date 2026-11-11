package dev.anip.service;

import dev.anip.core.ANIPError;
import dev.anip.core.AuditEntry;
import dev.anip.core.AuditFilters;
import dev.anip.core.AuditPolicy;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.Composition;
import dev.anip.core.CompositionStep;
import dev.anip.core.Constants;
import dev.anip.core.DelegationToken;
import dev.anip.core.FailurePolicy;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Delegation enforcement (SPEC.md §3.2, §6.3 and the behavioral-conformance
 * list). Mirrors the Python reference in anip_server/delegation.py and the
 * cross-runtime suite in conformance/test_delegation.py.
 *
 * <ul>
 *   <li>Purpose binding: "a token issued for book_flight cannot invoke
 *       search_flights", even when its scope would cover both.</li>
 *   <li>Only the holder of a token (its subject) may delegate from it.</li>
 *   <li>A delegated token cannot widen its parent's scope or scope budget.</li>
 *   <li>Chains deeper than max_delegation_depth are rejected.</li>
 *   <li>A delegation token is a credential for delegating, never for root
 *       issuance.</li>
 * </ul>
 *
 * Composed capabilities (§4.6) must still work under those rules: each child
 * step runs with its own token, delegated from the caller's token and bound
 * to the child capability, and its audit entry links back to the parent
 * invocation.
 */
class DelegationEnforcementTest {

    private static final String HUMAN = "human:test@example.com";

    private ANIPService service;
    private final Map<String, DelegationToken> seenTokens = new ConcurrentHashMap<>();

    private static CapabilityDeclaration decl(String name, List<String> scope, List<String> modes) {
        return new CapabilityDeclaration(name, name, "1.0",
                List.<CapabilityInput>of(),
                new CapabilityOutput("object", List.of()),
                new SideEffect("read", "not_applicable"),
                scope, null, null, modes);
    }

    private CapabilityDef recording(String name, List<String> scope, List<String> modes,
                                    Map<String, Object> result) {
        return new CapabilityDef(decl(name, scope, modes), (ctx, params) -> {
            seenTokens.put(name, ctx.getToken());
            return result;
        });
    }

    private static Composition summaryComposition() {
        Map<String, Map<String, String>> inputMapping = new LinkedHashMap<>();
        inputMapping.put("select", Map.of("q", "$.input.q"));
        inputMapping.put("enrich", Map.of("items", "$.steps.select.output.items"));
        return new Composition("same_service",
                List.of(new CompositionStep("select", "select_cap"), new CompositionStep("enrich", "enrich_cap")),
                inputMapping,
                Map.of("count", "$.steps.enrich.output.count"),
                new FailurePolicy(), new AuditPolicy(true, true));
    }

    @BeforeEach
    void setUp() throws Exception {
        CapabilityDef summary = new CapabilityDef(
                decl("summary", List.of("inv.read"), List.of("sync"))
                        .setKind("composed").setComposition(summaryComposition()),
                (ctx, params) -> Map.of());

        service = new ANIPService(new ServiceConfig()
                .setServiceId("test-service")
                .setCapabilities(List.of(
                        recording("search_flights", List.of("travel.search"), List.of("sync", "streaming"),
                                Map.of("flights", List.of("FL-001"))),
                        recording("book_flight", List.of("travel.book"), List.of("sync", "streaming"),
                                Map.of("booking_id", "BK-001")),
                        recording("select_cap", List.of("inv.read"), List.of("sync"),
                                Map.of("items", List.of("a", "b"))),
                        recording("enrich_cap", List.of("inv.read"), List.of("sync"),
                                Map.of("count", 2)),
                        summary))
                .setStorage(":memory:")
                .setAuthenticate(bearer -> "test-key".equals(bearer) ? Optional.of(HUMAN) : Optional.empty())
                .setRetentionIntervalSeconds(-1));
        service.start();
    }

    @AfterEach
    void tearDown() {
        if (service != null) {
            service.shutdown();
        }
    }

    // --- helpers -------------------------------------------------------------

    private TokenResponse issue(String principal, String subject, List<String> scope,
                                String capability, String parentToken) throws Exception {
        return service.issueToken(principal,
                new TokenRequest(subject, scope, capability, null, parentToken, 2, null));
    }

    private DelegationToken issueBound(String capability, List<String> scope) throws Exception {
        return service.resolveBearerToken(issue(HUMAN, HUMAN, scope, capability, null).getToken());
    }

    private static AuditFilters allEntries() {
        return new AuditFilters(null, null, null, null, null, null, null, 1000);
    }

    @SuppressWarnings("unchecked")
    private static String failureType(Map<String, Object> result) {
        Object failure = result.get("failure");
        assertNotNull(failure, "expected a failure object, got " + result);
        return (String) ((Map<String, Object>) failure).get("type");
    }

    private static void assertIssuanceFails(String expectedType, org.junit.jupiter.api.function.Executable call) {
        ANIPError error = assertThrows(ANIPError.class, call,
                "expected issuance to fail with " + expectedType + ", but a token was issued");
        assertEquals(expectedType, error.getErrorType(), error.getDetail());
    }

    // --- purpose binding -----------------------------------------------------

    @Test
    void invokeRejectsTokenBoundToAnotherCapability() throws Exception {
        // Scope covers both capabilities; the token is bound to book_flight.
        DelegationToken token = issueBound("book_flight", List.of("travel.search", "travel.book"));

        Map<String, Object> result = service.invoke("search_flights", token, Map.of(), new InvokeOpts());

        assertEquals(false, result.get("success"), "a token bound to book_flight was accepted for search_flights");
        assertEquals(Constants.FAILURE_PURPOSE_MISMATCH, failureType(result));
        assertNull(seenTokens.get("search_flights"), "the handler must not run");

        List<AuditEntry> entries = service.queryAudit(token, allEntries()).getEntries();
        assertEquals(1, entries.size());
        assertEquals("search_flights", entries.get(0).getCapability());
        assertFalse(entries.get(0).isSuccess());
        assertEquals(Constants.FAILURE_PURPOSE_MISMATCH, entries.get(0).getFailureType());
    }

    @Test
    void invokeStreamRejectsTokenBoundToAnotherCapability() throws Exception {
        DelegationToken token = issueBound("book_flight", List.of("travel.search", "travel.book"));

        ANIPError error = assertThrows(ANIPError.class,
                () -> service.invokeStream("search_flights", token, Map.of(), new InvokeOpts().setStream(true)));

        assertEquals(Constants.FAILURE_PURPOSE_MISMATCH, error.getErrorType());
    }

    // --- delegated issuance ---------------------------------------------------

    @Test
    void holderDelegatesWithinScope() throws Exception {
        TokenResponse root = issue(HUMAN, HUMAN, List.of("travel.search", "travel.book"), "search_flights", null);

        TokenResponse child = issue(HUMAN, "agent:helper", List.of("travel.search"), "search_flights",
                root.getTokenId());

        DelegationToken token = service.resolveBearerToken(child.getToken());
        assertEquals(root.getTokenId(), token.getParent());
        assertEquals(HUMAN, token.getRootPrincipal());
    }

    @Test
    void delegationByNonHolderIsRejected() throws Exception {
        TokenResponse root = issue(HUMAN, HUMAN, List.of("travel.search"), "search_flights", null);

        assertIssuanceFails(Constants.FAILURE_INSUFFICIENT_AUTHORITY,
                () -> issue("agent:someone-else", null, List.of("travel.search"), "search_flights",
                        root.getTokenId()));
    }

    @Test
    void delegatedTokenCannotWidenScope() throws Exception {
        TokenResponse root = issue(HUMAN, HUMAN, List.of("travel.search"), "search_flights", null);

        assertIssuanceFails(Constants.FAILURE_SCOPE_ESCALATION,
                () -> issue(HUMAN, null, List.of("travel.search", "travel.book"), "book_flight",
                        root.getTokenId()));
    }

    @Test
    void scopeNarrowingRules() throws Exception {
        record Case(String name, List<String> parent, List<String> child, boolean allowed) {}
        List<Case> cases = List.of(
                new Case("same scope", List.of("travel.search"), List.of("travel.search"), true),
                new Case("sub-scope of parent", List.of("travel"), List.of("travel.search"), true),
                new Case("sibling scope", List.of("travel.search"), List.of("travel.book"), false),
                new Case("prefix without a dot boundary", List.of("travel"), List.of("travelogue.read"), false),
                new Case("keeps scope budget", List.of("travel.book:max_$500"), List.of("travel.book:max_$500"), true),
                new Case("lowers scope budget", List.of("travel.book:max_$500"), List.of("travel.book:max_$100"), true),
                new Case("drops scope budget", List.of("travel.book:max_$500"), List.of("travel.book"), false),
                new Case("raises scope budget", List.of("travel.book:max_$500"), List.of("travel.book:max_$900"), false),
                // A budget that is not a finite, non-negative number must fail closed: NaN compares
                // false against everything, so it would pass a naive "child > parent" check.
                new Case("NaN scope budget", List.of("travel.book:max_$500"), List.of("travel.book:max_$NaN"), false),
                new Case("infinite scope budget", List.of("travel.book:max_$500"), List.of("travel.book:max_$Infinity"), false),
                new Case("negative scope budget", List.of("travel.book:max_$500"), List.of("travel.book:max_$-1"), false),
                new Case("unparseable scope budget", List.of("travel.book:max_$500"), List.of("travel.book:max_$lots"), false));

        for (Case c : cases) {
            TokenResponse root = issue(HUMAN, HUMAN, c.parent(), "book_flight", null);
            if (c.allowed()) {
                assertDoesNotThrow(() -> issue(HUMAN, null, c.child(), "book_flight", root.getTokenId()), c.name());
            } else {
                ANIPError error = assertThrows(ANIPError.class,
                        () -> issue(HUMAN, null, c.child(), "book_flight", root.getTokenId()), c.name());
                assertEquals(Constants.FAILURE_SCOPE_ESCALATION, error.getErrorType(), c.name());
            }
        }
    }

    // --- delegation depth -----------------------------------------------------

    @Test
    void invokeEnforcesDelegationDepth() throws Exception {
        TokenResponse token = issue(HUMAN, HUMAN, List.of("travel.search"), "search_flights", null);

        // The default max_delegation_depth is 3: depths 1..3 work, depth 4 does not.
        for (int depth = 1; depth <= 4; depth++) {
            token = issue(HUMAN, null, List.of("travel.search"), "search_flights", token.getTokenId());
            Map<String, Object> result = service.invoke("search_flights",
                    service.resolveBearerToken(token.getToken()), Map.of(), new InvokeOpts());
            if (depth <= 3) {
                assertEquals(true, result.get("success"), "depth " + depth + " is within the limit: " + result);
            } else {
                assertEquals(false, result.get("success"), "a token at delegation depth 4 was accepted (limit is 3)");
                assertEquals(Constants.FAILURE_DELEGATION_DEPTH_EXCEEDED, failureType(result));
            }
        }
    }

    // --- who may ask for a token ------------------------------------------------

    @Test
    void authenticateIssuerAcceptsBootstrapCredentialAndTokens() throws Exception {
        Optional<Issuer> bootstrap = service.authenticateIssuer("test-key");
        assertTrue(bootstrap.isPresent());
        assertEquals(HUMAN, bootstrap.get().principal());
        assertFalse(bootstrap.get().viaToken());

        TokenResponse held = issue(HUMAN, "agent:helper", List.of("travel.search"), "search_flights", null);
        Optional<Issuer> viaToken = service.authenticateIssuer(held.getToken());
        assertTrue(viaToken.isPresent());
        assertEquals("agent:helper", viaToken.get().principal());
        assertTrue(viaToken.get().viaToken());

        assertTrue(service.authenticateIssuer("not-a-credential").isEmpty());
    }

    @Test
    void tokenCredentialCannotIssueRootToken() throws Exception {
        TokenResponse held = issue(HUMAN, "agent:helper", List.of("travel.search"), "search_flights", null);
        Issuer issuer = service.authenticateIssuer(held.getToken()).orElseThrow();

        // No parent_token: this asks for a root token, with more scope than
        // the agent was ever given.
        assertIssuanceFails(Constants.FAILURE_INSUFFICIENT_AUTHORITY,
                () -> service.issueTokenAs(issuer, new TokenRequest(
                        null, List.of("travel.search", "travel.book"), "book_flight", null, null, 2, null)));
    }

    @Test
    void holderDelegatesWithTokenCredential() throws Exception {
        TokenResponse held = issue(HUMAN, "agent:helper", List.of("travel.search"), "search_flights", null);
        Issuer issuer = service.authenticateIssuer(held.getToken()).orElseThrow();

        TokenResponse child = service.issueTokenAs(issuer, new TokenRequest(
                "agent:sub-helper", List.of("travel.search"), "search_flights", null, held.getTokenId(), 2, null));

        DelegationToken token = service.resolveBearerToken(child.getToken());
        assertEquals(HUMAN, token.getRootPrincipal());
        assertEquals("agent:helper", token.getIssuer());
    }

    @Test
    void bootstrapCredentialIssuesRootToken() throws Exception {
        Issuer issuer = service.authenticateIssuer("test-key").orElseThrow();

        TokenResponse root = service.issueTokenAs(issuer, new TokenRequest(
                null, List.of("travel.search"), "search_flights", null, null, 2, null));

        assertTrue(root.isIssued());
    }

    // --- composed capabilities --------------------------------------------------

    @Test
    void composedInvocationRunsChildrenWithChildBoundTokens() throws Exception {
        DelegationToken token = issueBound("summary", List.of("inv.read"));

        Map<String, Object> result = service.invoke("summary", token, Map.of("q", "x"), new InvokeOpts());

        assertEquals(true, result.get("success"), "the composed invocation should succeed: " + result);
        String parentInvocationId = (String) result.get("invocation_id");

        for (String child : List.of("select_cap", "enrich_cap")) {
            DelegationToken childToken = seenTokens.get(child);
            assertNotNull(childToken, "child " + child + " was not invoked");
            assertEquals(child, childToken.getPurpose().getCapability(),
                    "child " + child + " must run with a token bound to it");
            assertEquals(token.getTokenId(), childToken.getParent(),
                    "child " + child + " token must be delegated from the caller's token");
        }

        Map<String, AuditEntry> byCapability = new LinkedHashMap<>();
        for (AuditEntry entry : service.queryAudit(token, allEntries()).getEntries()) {
            byCapability.put(entry.getCapability(), entry);
        }
        AuditEntry parentEntry = byCapability.get("summary");
        assertNotNull(parentEntry, "no audit entry for the parent");
        for (String child : List.of("select_cap", "enrich_cap")) {
            AuditEntry entry = byCapability.get(child);
            assertNotNull(entry, "no audit entry for child " + child);
            assertTrue(entry.isSuccess(), "child " + child + " failed: " + entry.getFailureType());
            assertEquals(parentInvocationId, entry.getParentInvocationId(),
                    "child " + child + " must link to the parent invocation");
            assertNotNull(entry.getTaskId());
            assertEquals(parentEntry.getTaskId(), entry.getTaskId(),
                    "child " + child + " must share the parent's task_id");
        }
    }
}
