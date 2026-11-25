package dev.anip.servicetest;

import dev.anip.core.BindingRequirement;
import dev.anip.core.Budget;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.Constants;
import dev.anip.core.Cost;
import dev.anip.core.DelegationToken;
import dev.anip.core.FinancialCost;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenRequest;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.InvokeOpts;
import dev.anip.service.ServiceConfig;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * SPEC.md §6.3 "Budget Enforcement": budget is a pre-execution MUST reject.
 * A capability with an estimated cost takes its check amount from the bound
 * price; when the binding carries no numeric price the budget cannot be
 * enforced and the call is refused before the handler.
 */
class BudgetBindingPriceTest {

    private ANIPService service;
    private final AtomicInteger calls = new AtomicInteger();

    @BeforeEach
    void setUp() throws Exception {
        CapabilityDeclaration book = new CapabilityDeclaration(
                "book", "Book", "1.0",
                List.of(
                        new CapabilityInput("flight", "string", true, "flight"),
                        new CapabilityInput("quote_id", "object", false, "priced quote")),
                new CapabilityOutput("object", List.of("booking_id")),
                new SideEffect("irreversible", "none"),
                List.of("travel.book"),
                new Cost("estimated", new FinancialCost("USD", null, 280.0, 500.0, null, null),
                        "search", null, null, null),
                null, List.of("unary"),
                List.of(new BindingRequirement("quote", "quote_id", "search", null)),
                List.of());
        service = new ANIPService(new ServiceConfig()
                .setServiceId("budget-binding-test")
                .setStorage(":memory:")
                .setCapabilities(List.of(new CapabilityDef(book, (ctx, params) -> {
                    calls.incrementAndGet();
                    return Map.of("booking_id", "BK-1");
                })))
                .setAuthenticate(b -> "valid".equals(b) ? Optional.of("alice") : Optional.empty())
                .setRetentionIntervalSeconds(-1));
        service.start();
    }

    @AfterEach
    void tearDown() {
        if (service != null) service.shutdown();
    }

    private DelegationToken token(Budget budget) throws Exception {
        return service.resolveBearerToken(service.issueToken("alice", new TokenRequest(
                "agent", List.of("travel.book"), "book", null, null, 1, null, budget)).getToken());
    }

    private static Map<String, Object> parameters(Map<String, Object> quote) {
        Map<String, Object> p = new LinkedHashMap<>();
        p.put("flight", "AA100");
        if (quote != null) {
            p.put("quote_id", quote);
        }
        return p;
    }

    @SuppressWarnings("unchecked")
    private void assertNotEnforceable(Map<String, Object> response) {
        assertEquals(false, response.get("success"), String.valueOf(response));
        Map<String, Object> failure = (Map<String, Object>) response.get("failure");
        assertEquals(Constants.FAILURE_BUDGET_NOT_ENFORCEABLE, failure.get("type"), String.valueOf(failure));
        assertEquals("Capability book has estimated cost with requires_binding but the provided "
                + "binding does not carry a resolvable price", failure.get("detail"));
        Map<String, Object> resolution = (Map<String, Object>) failure.get("resolution");
        assertEquals("obtain_binding", resolution.get("action"));
        assertEquals("refresh_then_retry", resolution.get("recovery_class"));
        assertEquals("binding value must include a 'price' field or the service must resolve "
                + "binding to a concrete price", resolution.get("requires"));
        assertEquals(false, failure.get("retry"));
        assertNull(response.get("result"));
        assertEquals(403, Constants.failureStatusCode((String) failure.get("type")));
        assertEquals(0, calls.get(), "the handler must not run");
    }

    @Test
    void bindingWithoutAPriceIsRefusedWhenTheTokenHasABudget() throws Exception {
        Map<String, Object> response = service.invoke("book", token(new Budget("USD", 1)),
                parameters(Map.of("id", "qt-1", "issued_at", System.currentTimeMillis() / 1000)),
                new InvokeOpts());
        assertNotEnforceable(response);
    }

    @Test
    void bindingWithANonNumericPriceIsRefused() throws Exception {
        for (Object price : List.of("420", true, List.of(420), Map.of("amount", 420))) {
            Map<String, Object> response = service.invoke("book", token(new Budget("USD", 100000)),
                    parameters(Map.of("id", "qt-1", "price", price)), new InvokeOpts());
            assertNotEnforceable(response);
        }
    }

    @Test
    void bindingThatIsNotAnObjectIsRefusedForTheBudget() throws Exception {
        Map<String, Object> p = parameters(null);
        p.put("quote_id", null);
        assertNotEnforceable(service.invoke("book", token(new Budget("USD", 100000)), p, new InvokeOpts()));
        assertNotEnforceable(service.invoke("book", token(new Budget("USD", 100000)),
                parameters(null), new InvokeOpts()));
    }

    @Test
    void aRequestBudgetIsEnforcedTheSameWay() throws Exception {
        InvokeOpts opts = new InvokeOpts();
        opts.setBudget(new Budget("USD", 1));
        assertNotEnforceable(service.invoke("book", token(null),
                parameters(Map.of("id", "qt-1")), opts));
    }

    @SuppressWarnings("unchecked")
    @Test
    void aBoundPriceIsCheckedAgainstTheBudget() throws Exception {
        Map<String, Object> over = service.invoke("book", token(new Budget("USD", 1)),
                parameters(Map.of("id", "qt-1", "price", 420)), new InvokeOpts());
        assertEquals(Constants.FAILURE_BUDGET_EXCEEDED,
                ((Map<String, Object>) over.get("failure")).get("type"));
        assertEquals(0, calls.get());

        Map<String, Object> within = service.invoke("book", token(new Budget("USD", 500)),
                parameters(Map.of("id", "qt-1", "price", 420.0)), new InvokeOpts());
        assertEquals(true, within.get("success"), String.valueOf(within));
        assertEquals(1, calls.get());
    }

    @Test
    void withoutABudgetTheBindingNeedsNoPrice() throws Exception {
        Map<String, Object> response = service.invoke("book", token(null),
                parameters(Map.of("id", "qt-1")), new InvokeOpts());
        assertEquals(true, response.get("success"), String.valueOf(response));
        assertEquals(1, calls.get());
    }
}
