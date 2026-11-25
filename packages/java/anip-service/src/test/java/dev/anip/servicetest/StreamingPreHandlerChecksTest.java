package dev.anip.servicetest;

import dev.anip.core.ANIPError;
import dev.anip.core.AuditEntry;
import dev.anip.core.AuditFilters;
import dev.anip.core.BindingRequirement;
import dev.anip.core.Budget;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.Constants;
import dev.anip.core.ControlRequirement;
import dev.anip.core.Cost;
import dev.anip.core.DelegationToken;
import dev.anip.core.FinancialCost;
import dev.anip.core.GrantPolicy;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenRequest;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.InvokeOpts;
import dev.anip.service.ServiceConfig;
import dev.anip.service.StreamEvent;
import dev.anip.service.StreamResult;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

/**
 * A streaming invocation passes the same checks before its handler as a unary
 * one (SPEC.md §6.3): for the same request both paths refuse with the same
 * failure, the handler does not run, no grant is reserved, and the refusal is
 * audited where the unary refusal is audited.
 */
class StreamingPreHandlerChecksTest {

    private ANIPService service;
    private final AtomicInteger calls = new AtomicInteger();

    private CapabilityDef capability(CapabilityDeclaration declaration) {
        return new CapabilityDef(declaration, (ctx, params) -> {
            calls.incrementAndGet();
            return Map.of("ok", true);
        });
    }

    @BeforeEach
    void setUp() throws Exception {
        List<String> modes = List.of("unary", "streaming");
        // Estimated cost, priced by a binding that goes stale.
        CapabilityDeclaration book = new CapabilityDeclaration(
                "book", "Book", "1.0",
                List.of(
                        new CapabilityInput("flight", "string", true, "flight"),
                        new CapabilityInput("quote_id", "object", false, "priced quote")),
                new CapabilityOutput("object", List.of()),
                new SideEffect("irreversible", "none"),
                List.of("travel.book"),
                new Cost("estimated", new FinancialCost("USD", null, 280.0, 500.0, null, null),
                        "search", null, null, null),
                null, modes,
                List.of(new BindingRequirement("quote", "quote_id", "search", "PT15M")),
                List.of())
                .setGrantPolicy(new GrantPolicy(List.of("one_time"), "one_time", 600, 1));
        CapabilityDeclaration ceiling = new CapabilityDeclaration(
                "ceiling", "Needs a cost ceiling", "1.0",
                List.of(),
                new CapabilityOutput("object", List.of()),
                new SideEffect("read", "not_applicable"),
                List.of("travel.book"), null, null, modes,
                null,
                List.of(new ControlRequirement("cost_ceiling", "reject")));
        CapabilityDeclaration other = new CapabilityDeclaration(
                "other", "Another capability", "1.0",
                List.of(),
                new CapabilityOutput("object", List.of()),
                new SideEffect("read", "not_applicable"),
                List.of("travel.book"), null, null, modes);

        service = new ANIPService(new ServiceConfig()
                .setServiceId("stream-checks-test")
                .setStorage(":memory:")
                .setCapabilities(List.of(capability(book), capability(ceiling), capability(other)))
                .setAuthenticate(b -> "valid".equals(b) ? Optional.of("alice") : Optional.empty())
                .setRetentionIntervalSeconds(-1));
        service.start();
    }

    @AfterEach
    void tearDown() {
        if (service != null) service.shutdown();
    }

    private DelegationToken token(String capability, List<String> scope, Budget budget) throws Exception {
        return service.resolveBearerToken(service.issueToken("alice", new TokenRequest(
                "agent", scope, capability, null, null, 1, null, budget)).getToken());
    }

    private static Map<String, Object> booking(Map<String, Object> quote) {
        Map<String, Object> p = new LinkedHashMap<>();
        p.put("flight", "AA100");
        if (quote != null) {
            p.put("quote_id", quote);
        }
        return p;
    }

    private static Map<String, Object> freshQuote(Object price) {
        Map<String, Object> quote = new LinkedHashMap<>();
        quote.put("id", "qt-1");
        quote.put("issued_at", System.currentTimeMillis() / 1000);
        if (price != null) {
            quote.put("price", price);
        }
        return quote;
    }

    @SuppressWarnings("unchecked")
    private static String failureType(Map<String, Object> response) {
        Object failure = response.get("failure");
        return failure instanceof Map<?, ?> f ? String.valueOf(f.get("type")) : null;
    }

    /** What a unary invocation answers: the failure type, or that the handler ran. */
    private String unary(String capability, DelegationToken token, Map<String, Object> parameters,
                         InvokeOpts opts) {
        Map<String, Object> response = service.invoke(capability, token, parameters, opts);
        return Boolean.TRUE.equals(response.get("success")) ? "handler ran" : failureType(response);
    }

    /** What a streaming invocation answers: the failure type, or that the handler ran. */
    private String streaming(String capability, DelegationToken token, Map<String, Object> parameters,
                             InvokeOpts opts) throws Exception {
        StreamResult result;
        try {
            result = service.invokeStream(capability, token, parameters, opts);
        } catch (ANIPError e) {
            return e.getErrorType();
        }
        List<StreamEvent> events = new ArrayList<>();
        while (true) {
            StreamEvent event = result.getEvents().poll(5, TimeUnit.SECONDS);
            assertNotNull(event, "timed out waiting for a stream event");
            if (StreamResult.DONE_TYPE.equals(event.getType())) break;
            events.add(event);
        }
        StreamEvent last = events.get(events.size() - 1);
        return "completed".equals(last.getType()) ? "handler ran" : failureType(last.getPayload());
    }

    private int auditEntries(String failureType) throws Exception {
        int count = 0;
        for (AuditEntry entry : service.getStorage().queryAuditEntries(
                new AuditFilters(null, null, null, null, null, null, null, 100))) {
            if (failureType.equals(entry.getFailureType())) count++;
        }
        return count;
    }

    /**
     * Runs the same request on both paths. The unary answer is the expected
     * failure; the streaming answer must be the same, the handler must not
     * run on either path, and the streaming refusal must add as many audit
     * entries as the unary one did.
     */
    private void assertSameRefusal(String expected, String capability, Supplier<DelegationToken> token,
                                   Map<String, Object> parameters, Supplier<InvokeOpts> opts) throws Exception {
        assertEquals(expected, unary(capability, token.get(), parameters, opts.get()), "unary path");
        int auditedByUnary = auditEntries(expected);
        assertEquals(0, calls.get(), "unary path: the handler must not run");

        String answered = streaming(capability, token.get(), parameters, opts.get());
        assertEquals(expected, answered, "streaming path answered: " + answered
                + (calls.get() > 0 ? " (the handler ran)" : ""));
        assertEquals(0, calls.get(), "streaming path: the handler must not run");
        assertEquals(auditedByUnary, auditEntries(expected) - auditedByUnary,
                "streaming path: audit entries for " + expected);
    }

    private Supplier<DelegationToken> bookToken(Budget budget) {
        return () -> {
            try {
                return token("book", List.of("travel.book"), budget);
            } catch (Exception e) {
                throw new IllegalStateException(e);
            }
        };
    }

    private static Supplier<InvokeOpts> noOptions() {
        return InvokeOpts::new;
    }

    private static Supplier<InvokeOpts> withGrant(String grant) {
        return () -> new InvokeOpts().setApprovalGrant(grant);
    }

    // --- one test per row of the round-two table ---

    @Test
    void row01BudgetExceeded() throws Exception {
        assertSameRefusal(Constants.FAILURE_BUDGET_EXCEEDED, "book",
                bookToken(new Budget("USD", 1)), booking(freshQuote(420)), noOptions());
    }

    @Test
    void row02BudgetNotEnforceable() throws Exception {
        assertSameRefusal(Constants.FAILURE_BUDGET_NOT_ENFORCEABLE, "book",
                bookToken(new Budget("USD", 100000)), booking(freshQuote(null)), noOptions());
    }

    @Test
    void row03BindingMissing() throws Exception {
        assertSameRefusal(Constants.FAILURE_BINDING_MISSING, "book",
                bookToken(null), booking(null), noOptions());
    }

    @Test
    void row04BindingStale() throws Exception {
        Map<String, Object> stale = freshQuote(420);
        stale.put("issued_at", System.currentTimeMillis() / 1000 - 3600);
        assertSameRefusal(Constants.FAILURE_BINDING_STALE, "book",
                bookToken(null), booking(stale), noOptions());
    }

    @Test
    void row05ControlRequirementUnsatisfied() throws Exception {
        assertSameRefusal(Constants.FAILURE_CONTROL_REQUIREMENT_UNSATISFIED, "ceiling",
                () -> {
                    try {
                        return token("ceiling", List.of("travel.book"), null);
                    } catch (Exception e) {
                        throw new IllegalStateException(e);
                    }
                }, Map.of(), noOptions());
    }

    @Test
    void row06PurposeMismatch() throws Exception {
        // The token is bound to another capability.
        assertSameRefusal(Constants.FAILURE_PURPOSE_MISMATCH, "book",
                () -> {
                    try {
                        return token("other", List.of("travel.book"), null);
                    } catch (Exception e) {
                        throw new IllegalStateException(e);
                    }
                }, booking(freshQuote(420)), noOptions());
    }

    @Test
    void row07InsufficientScope() throws Exception {
        assertSameRefusal(Constants.FAILURE_SCOPE_INSUFFICIENT, "book",
                () -> {
                    try {
                        return token("book", List.of("travel.search"), null);
                    } catch (Exception e) {
                        throw new IllegalStateException(e);
                    }
                }, booking(freshQuote(420)), noOptions());
    }

    @Test
    void row08BlankApprovalGrant() throws Exception {
        assertSameRefusal(Constants.FAILURE_GRANT_NOT_FOUND, "book",
                bookToken(null), booking(freshQuote(420)), withGrant(""));
    }

    @Test
    void row09UnknownApprovalGrant() throws Exception {
        assertSameRefusal(Constants.FAILURE_GRANT_NOT_FOUND, "book",
                bookToken(null), booking(freshQuote(420)), withGrant("grant_0123456789ab"));
    }

    @Test
    void row10ParameterValidation() throws Exception {
        Map<String, Object> parameters = booking(freshQuote(420));
        parameters.remove("flight");
        assertSameRefusal(Constants.FAILURE_INVALID_PARAMETERS, "book",
                bookToken(null), parameters, noOptions());
    }

    /** Control: a valid request runs the handler on both paths. */
    @Test
    void aValidRequestRunsTheHandlerOnBothPaths() throws Exception {
        assertEquals("handler ran", unary("book", bookToken(new Budget("USD", 500)).get(),
                booking(freshQuote(420)), new InvokeOpts()));
        assertEquals("handler ran", streaming("book", bookToken(new Budget("USD", 500)).get(),
                booking(freshQuote(420)), new InvokeOpts()));
        assertEquals(2, calls.get());
    }
}
