package dev.anip.servicetest;

import dev.anip.core.ANIPError;
import dev.anip.core.AuditEntry;
import dev.anip.core.AuditFilters;
import dev.anip.core.BindingRequirement;
import dev.anip.core.Budget;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.ControlRequirement;
import dev.anip.core.Cost;
import dev.anip.core.DelegationToken;
import dev.anip.core.FinancialCost;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenRequest;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.EventClassification;
import dev.anip.service.InvokeOpts;
import dev.anip.service.ServiceConfig;
import dev.anip.service.StreamEvent;
import dev.anip.service.StreamResult;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Stream;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import static org.junit.jupiter.api.Assertions.*;

/**
 * SPEC.md §6.3: every refusal made before the handler is audited. Budget,
 * binding and control-requirement refusals are recorded like scope,
 * purpose and parameter refusals, on unary and streaming invocations.
 */
class PrehandlerAuditTest {

    private ANIPService service;
    private final AtomicInteger calls = new AtomicInteger();

    @AfterEach
    void tearDown() {
        if (service != null) service.shutdown();
    }

    private static final Cost FIXED = new Cost("fixed", new FinancialCost("USD", 500.0), null, null, null, null);
    private static final Cost ESTIMATED = new Cost("estimated",
            new FinancialCost("USD", null, 100.0, 500.0, null, null), null, null, null, null);
    private static final List<BindingRequirement> QUOTE =
            List.of(new BindingRequirement("quote", "quote", null, "PT15M"));

    static Stream<Arguments> cases() {
        long now = System.currentTimeMillis() / 1000;
        List<Arguments> cases = new ArrayList<>();
        for (boolean stream : List.of(false, true)) {
            cases.add(Arguments.of("budget_exceeded", FIXED, List.of(), List.of(), Map.of(),
                    new Budget("USD", 1), stream));
            cases.add(Arguments.of("budget_exceeded", ESTIMATED, QUOTE, List.of(),
                    Map.of("quote", Map.of("price", 420, "issued_at", now)), new Budget("USD", 100), stream));
            cases.add(Arguments.of("budget_currency_mismatch", FIXED, List.of(), List.of(), Map.of(),
                    new Budget("EUR", 1000), stream));
            cases.add(Arguments.of("budget_not_enforceable", ESTIMATED, QUOTE, List.of(),
                    Map.of("quote", Map.of("issued_at", now)), new Budget("USD", 1000), stream));
            cases.add(Arguments.of("binding_missing", ESTIMATED, QUOTE, List.of(), Map.of(), null, stream));
            cases.add(Arguments.of("binding_stale", ESTIMATED, QUOTE, List.of(),
                    Map.of("quote", Map.of("price", 420, "issued_at", now - 86400)), null, stream));
            cases.add(Arguments.of("control_requirement_unsatisfied", null, List.of(),
                    List.of(new ControlRequirement("cost_ceiling", "reject")), Map.of(), null, stream));
        }
        return cases.stream();
    }

    private DelegationToken start(Cost cost, List<BindingRequirement> bindings,
                                  List<ControlRequirement> controls) throws Exception {
        CapabilityDeclaration decl = new CapabilityDeclaration("book", "book", "1.0",
                List.of(new CapabilityInput("quote", "object", false, "quote")),
                new CapabilityOutput("object", List.of("ok")),
                new SideEffect("irreversible", "none"),
                List.of("book"), cost, null, List.of("unary", "streaming"),
                bindings, controls);
        service = new ANIPService(new ServiceConfig()
                .setServiceId("test-prehandler-audit")
                .setCapabilities(List.of(new CapabilityDef(decl, (ctx, params) -> {
                    calls.incrementAndGet();
                    return Map.of("ok", true);
                })))
                .setStorage(":memory:")
                .setRetentionIntervalSeconds(-1));
        service.start();
        return service.resolveBearerToken(service.issueToken("alice",
                new TokenRequest("alice", List.of("book"), "book", null, null, 1, null)).getToken());
    }

    @ParameterizedTest(name = "{0} stream={6}")
    @MethodSource("cases")
    void refusalBeforeTheHandlerIsAudited(String expected, Cost cost, List<BindingRequirement> bindings,
                                          List<ControlRequirement> controls, Map<String, Object> params,
                                          Budget budget, boolean stream) throws Exception {
        DelegationToken token = start(cost, bindings, controls);
        InvokeOpts opts = new InvokeOpts("ref-audit", stream).setBudget(budget);

        if (stream) {
            Map<String, Object> failure;
            try {
                StreamResult result = service.invokeStream("book", token, new HashMap<>(params), opts);
                StreamEvent event = result.getEvents().poll(5, TimeUnit.SECONDS);
                assertNotNull(event);
                assertEquals("failed", event.getType());
                @SuppressWarnings("unchecked")
                Map<String, Object> f = (Map<String, Object>) event.getPayload().get("failure");
                failure = f;
                assertEquals(expected, failure.get("type"));
            } catch (ANIPError e) {
                assertEquals(expected, e.getErrorType());
                assertNotNull(e.getResolution(), "the failure carries a resolution");
            }
        } else {
            Map<String, Object> response = service.invoke("book", token, new HashMap<>(params), opts);
            assertEquals(false, response.get("success"));
            @SuppressWarnings("unchecked")
            Map<String, Object> failure = (Map<String, Object>) response.get("failure");
            assertEquals(expected, failure.get("type"));
            @SuppressWarnings("unchecked")
            Map<String, Object> resolution = (Map<String, Object>) failure.get("resolution");
            assertNotNull(resolution, "SPEC.md §4.5: every failure carries a resolution: " + failure);
            assertNotNull(resolution.get("recovery_class"));
        }
        assertEquals(0, calls.get(), "the handler must not run");

        List<AuditEntry> entries = service.queryAudit(token,
                new AuditFilters(null, null, null, "ref-audit", 50)).getEntries();
        assertEquals(1, entries.size(), "one audit entry for the " + expected + " refusal");
        AuditEntry entry = entries.get(0);
        assertFalse(entry.isSuccess());
        assertEquals(expected, entry.getFailureType());
        assertEquals(EventClassification.classify("irreversible", false, expected), entry.getEventClass());
    }
}
