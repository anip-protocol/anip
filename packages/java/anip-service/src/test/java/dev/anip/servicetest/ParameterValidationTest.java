package dev.anip.servicetest;

import com.fasterxml.jackson.databind.ObjectMapper;

import dev.anip.core.ANIPError;
import dev.anip.core.ApprovalGrant;
import dev.anip.core.AuditEntry;
import dev.anip.core.AuditFilters;
import dev.anip.core.AuditPolicy;
import dev.anip.core.BindingRequirement;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.Composition;
import dev.anip.core.CompositionStep;
import dev.anip.core.Constants;
import dev.anip.core.DelegationToken;
import dev.anip.core.FailurePolicy;
import dev.anip.core.GrantPolicy;
import dev.anip.core.InputResolution;
import dev.anip.core.ResolutionBehavior;
import dev.anip.core.ResolutionMode;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.InvokeOpts;
import dev.anip.service.ParameterValidation;
import dev.anip.service.ServiceConfig;
import dev.anip.service.StreamEvent;
import dev.anip.service.StreamResult;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * SPEC.md §6.3 "Parameter Validation": the invocation's parameters are
 * checked against the capability's declared inputs before the handler runs,
 * for unary and streaming invocations.
 */
class ParameterValidationTest {

    private static final Map<String, Object> RESOLUTION = Map.of(
            "action", "retry_now",
            "recovery_class", "retry_now",
            "requires", "parameters that match the capability's declared inputs");

    private ANIPService service;
    private final AtomicInteger typedCalls = new AtomicInteger();
    private final AtomicInteger sensitiveCalls = new AtomicInteger();
    private final AtomicInteger boundCalls = new AtomicInteger();
    private final AtomicInteger childCalls = new AtomicInteger();
    private final AtomicInteger resolvedCalls = new AtomicInteger();
    private final AtomicReference<Map<String, Object>> lastTypedParams = new AtomicReference<>();

    private static CapabilityDeclaration declaration(String name, List<CapabilityInput> inputs,
                                                     List<String> scope, List<String> modes) {
        return new CapabilityDeclaration(name, name, "1.0", inputs,
                new CapabilityOutput("object", List.of()),
                new SideEffect("read", "not_applicable"),
                scope, null, null, modes);
    }

    @BeforeEach
    void setUp() throws Exception {
        CapabilityDeclaration typed = declaration("typed", List.of(
                new CapabilityInput("s", "string", true, "a string"),
                new CapabilityInput("i", "integer", true, "an integer"),
                new CapabilityInput("n", "number", false, "a number"),
                new CapabilityInput("b", "boolean", false, "a boolean"),
                new CapabilityInput("a", "array", false, "an array"),
                new CapabilityInput("o", "object", false, "an object"),
                new CapabilityInput("code", "airport_code", false, "a domain type"),
                new CapabilityInput("upper", "String", false, "not a primitive name")
        ), List.of("typed"), List.of("unary", "streaming"));

        CapabilityDeclaration resolved = declaration("resolved", List.of(
                // The declaration says what happens when the value is absent.
                new CapabilityInput("ask", "string", true, null, "asks when absent", null, false,
                        null, null, null,
                        new InputResolution(ResolutionMode.CLARIFY, null, ResolutionBehavior.CLARIFY, null, null)),
                new CapabilityInput("plain", "string", true, "no resolution block"),
                // A resolution block that does not set on_missing.
                new CapabilityInput("mode_only", "string", true, null, "mode only", null, false,
                        null, null, null,
                        new InputResolution(ResolutionMode.EXPLICIT_ONLY, null, null,
                                ResolutionBehavior.CLARIFY, ResolutionBehavior.DENY))
        ), List.of("typed"), List.of("unary", "streaming"));

        CapabilityDeclaration defaulted = declaration("defaulted", List.of(
                new CapabilityInput("count", "integer", true, 1, "required, with a default")
        ), List.of("typed"), List.of("unary"));

        CapabilityDeclaration sensitive = declaration("sensitive", List.of(
                new CapabilityInput("memo", "string", true, "memo"),
                new CapabilityInput("amount", "integer", true, "amount")
        ), List.of("typed"), List.of("unary", "streaming"))
                .setGrantPolicy(new GrantPolicy(List.of("one_time"), "one_time", 600, 1));

        CapabilityDeclaration bound = new CapabilityDeclaration("bound", "bound", "1.0",
                List.of(
                        new CapabilityInput("flight", "string", true, "flight"),
                        new CapabilityInput("quote_id", "object", false, "quote")),
                new CapabilityOutput("object", List.of()),
                new SideEffect("read", "not_applicable"),
                List.of("typed"), null, null, List.of("unary"),
                List.of(new BindingRequirement("quote", "quote_id", "typed", null)),
                List.of());

        CapabilityDeclaration child = declaration("child", List.of(
                new CapabilityInput("needed", "string", true, "needed")
        ), List.of("typed"), List.of("unary"));

        CapabilityDeclaration parent = declaration("parent", List.of(
                new CapabilityInput("in", "string", true, "in")
        ), List.of("typed"), List.of("unary"))
                .setKind("composed")
                .setComposition(new Composition("same_service",
                        List.of(new CompositionStep("only", "child")),
                        // The step passes "other", not the child's required "needed".
                        Map.of("only", Map.of("other", "$.input.in")),
                        Map.of("out", "$.steps.only.output.ok"),
                        new FailurePolicy(), new AuditPolicy(true, true)));

        service = new ANIPService(new ServiceConfig()
                .setServiceId("validation-test")
                .setStorage(":memory:")
                .setCapabilities(List.of(
                        new CapabilityDef(typed, (ctx, params) -> {
                            typedCalls.incrementAndGet();
                            lastTypedParams.set(new LinkedHashMap<>(params));
                            return Map.of("ok", true);
                        }),
                        new CapabilityDef(defaulted, (ctx, params) -> Map.of("ok", true)),
                        new CapabilityDef(resolved, (ctx, params) -> {
                            resolvedCalls.incrementAndGet();
                            // The handler implements the on_missing path.
                            return Map.of("asked", params.get("ask") == null);
                        }),
                        new CapabilityDef(sensitive, (ctx, params) -> {
                            sensitiveCalls.incrementAndGet();
                            if (ctx.getApprovalGrant() == null) {
                                throw new ANIPError(Constants.FAILURE_APPROVAL_REQUIRED, "needs approval")
                                        .withResolution("request_approval");
                            }
                            return Map.of("ok", true);
                        }),
                        new CapabilityDef(bound, (ctx, params) -> {
                            boundCalls.incrementAndGet();
                            return Map.of("ok", true);
                        }),
                        new CapabilityDef(child, (ctx, params) -> {
                            childCalls.incrementAndGet();
                            return Map.of("ok", true);
                        }),
                        new CapabilityDef(parent, (ctx, params) -> Map.of())))
                .setAuthenticate(b -> "valid".equals(b) ? Optional.of("alice") : Optional.empty())
                .setRetentionIntervalSeconds(-1));
        service.start();
    }

    @AfterEach
    void tearDown() {
        if (service != null) service.shutdown();
    }

    private DelegationToken token(String capability, List<String> scope) throws Exception {
        return token(capability, scope, null);
    }

    private DelegationToken token(String capability, List<String> scope, String taskId) throws Exception {
        Map<String, Object> purpose = taskId != null ? new HashMap<>(Map.of("task_id", taskId)) : null;
        TokenResponse resp = service.issueToken("alice",
                new TokenRequest("agent", scope, capability, purpose, null, 2, null));
        return service.resolveBearerToken(resp.getToken());
    }

    private Map<String, Object> invokeTyped(Map<String, Object> params) throws Exception {
        return service.invoke("typed", token("typed", List.of("typed")), params, new InvokeOpts());
    }

    private static Map<String, Object> params(Object... keyValues) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int k = 0; k < keyValues.length; k += 2) {
            m.put((String) keyValues[k], keyValues[k + 1]);
        }
        return m;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> failure(Map<String, Object> response) {
        assertEquals(false, response.get("success"), "expected a refusal: " + response);
        return (Map<String, Object>) response.get("failure");
    }

    /** The response is exactly the §6.3 failure with the given detail. */
    private static void assertInvalid(Map<String, Object> response, String detail) {
        Map<String, Object> failure = failure(response);
        assertEquals(Constants.FAILURE_INVALID_PARAMETERS, failure.get("type"), String.valueOf(failure));
        assertEquals(detail, failure.get("detail"));
        assertEquals(RESOLUTION, failure.get("resolution"));
        assertEquals(false, failure.get("retry"));
        assertNull(response.get("result"));
        assertTrue(String.valueOf(response.get("invocation_id")).startsWith("inv-"));
    }

    private AuditEntry auditEntry(String capability, String invocationId) throws Exception {
        List<AuditEntry> entries = service.queryAudit(token(capability, List.of("typed")),
                new AuditFilters(null, null, invocationId, null, 50)).getEntries();
        assertEquals(1, entries.size(), "one audit entry for " + invocationId);
        return entries.get(0);
    }

    // --- required inputs ---

    @Test
    void missingRequiredInputsAreNamedInDeclarationOrder() throws Exception {
        InvokeOpts opts = new InvokeOpts("ref-1", false, "task-1", "inv-aaaaaaaaaaaa", "upstream");
        Map<String, Object> response = service.invoke("typed",
                token("typed", List.of("typed"), "task-1"), params("n", 1.5), opts);

        assertInvalid(response, "typed is missing required input(s): s, i");
        assertEquals("ref-1", response.get("client_reference_id"));
        assertEquals("task-1", response.get("task_id"));
        assertEquals("inv-aaaaaaaaaaaa", response.get("parent_invocation_id"));
        assertEquals("upstream", response.get("upstream_service"));
        assertEquals(0, typedCalls.get(), "the handler must not run");

        AuditEntry entry = auditEntry("typed", (String) response.get("invocation_id"));
        assertFalse(entry.isSuccess());
        assertEquals(Constants.FAILURE_INVALID_PARAMETERS, entry.getFailureType());
        assertEquals("typed", entry.getCapability());
        assertEquals("ref-1", entry.getClientReferenceId());
        assertEquals("task-1", entry.getTaskId());
        assertEquals("inv-aaaaaaaaaaaa", entry.getParentInvocationId());
    }

    @Test
    void oneMissingInputIsNamedAlone() throws Exception {
        assertInvalid(invokeTyped(params("s", "x")), "typed is missing required input(s): i");
    }

    @Test
    void nullForARequiredInputIsMissing() throws Exception {
        assertInvalid(invokeTyped(params("s", null, "i", 1)),
                "typed is missing required input(s): s");
        assertEquals(0, typedCalls.get());
    }

    @Test
    void absentParametersCountAsEmpty() throws Exception {
        assertInvalid(invokeTyped(null), "typed is missing required input(s): s, i");
        assertInvalid(invokeTyped(Map.of()), "typed is missing required input(s): s, i");
    }

    @Test
    void aDeclaredDefaultDoesNotSatisfyRequired() throws Exception {
        Map<String, Object> response = service.invoke("defaulted",
                token("defaulted", List.of("typed")), Map.of(), new InvokeOpts());
        assertInvalid(response, "defaulted is missing required input(s): count");
    }

    @Test
    void missingIsReportedBeforeWrongTypes() throws Exception {
        assertInvalid(invokeTyped(params("s", 5)), "typed is missing required input(s): i");
    }

    // --- inputs that declare resolution.on_missing (SPEC.md §6.3 exception, §4.10) ---

    private Map<String, Object> invokeResolved(Map<String, Object> params) throws Exception {
        return service.invoke("resolved", token("resolved", List.of("typed")), params, new InvokeOpts());
    }

    @Test
    void aRequiredInputThatDeclaresOnMissingReachesTheHandlerWhenAbsent() throws Exception {
        Map<String, Object> response = invokeResolved(params("plain", "p", "mode_only", "m"));
        assertEquals(true, response.get("success"), String.valueOf(response));
        assertEquals(Map.of("asked", true), response.get("result"));
        assertEquals(1, resolvedCalls.get());

        // JSON null is the same as leaving it out.
        response = invokeResolved(params("ask", null, "plain", "p", "mode_only", "m"));
        assertEquals(true, response.get("success"), String.valueOf(response));
        assertEquals(2, resolvedCalls.get());
    }

    @Test
    void theSameInputWithoutAResolutionBlockIsRefused() throws Exception {
        // 'ask' and 'plain' are both absent; only 'plain' is reported.
        assertInvalid(invokeResolved(params("mode_only", "m")),
                "resolved is missing required input(s): plain");
        assertEquals(0, resolvedCalls.get());
    }

    @Test
    void aResolutionBlockThatDoesNotSetOnMissingIsRefused() throws Exception {
        assertInvalid(invokeResolved(params("plain", "p")),
                "resolved is missing required input(s): mode_only");
        assertInvalid(invokeResolved(Map.of()),
                "resolved is missing required input(s): plain, mode_only");
        assertEquals(0, resolvedCalls.get());
    }

    @Test
    void aSuppliedValueForAnOnMissingInputIsStillTypeChecked() throws Exception {
        assertInvalid(invokeResolved(params("ask", 5, "plain", "p", "mode_only", "m")),
                "resolved has invalid input(s): 'ask' must be string, got number");
        assertEquals(0, resolvedCalls.get());

        Map<String, Object> response = invokeResolved(params("ask", "a", "plain", "p", "mode_only", "m"));
        assertEquals(Map.of("asked", false), response.get("result"));
    }

    @Test
    void everyOnMissingValueExemptsTheInput() {
        for (ResolutionBehavior behavior : ResolutionBehavior.values()) {
            // closed_values needs allowed_values and use_default a default: give both.
            CapabilityDeclaration decl = declaration("each", List.of(
                    new CapabilityInput("v", "string", true, "d", "v", null, false,
                            List.of("d"), null, null,
                            new InputResolution(ResolutionMode.CLOSED_VALUES, null, behavior, null, null))
            ), List.of("typed"), List.of("unary"));
            assertNull(ParameterValidation.check("each", decl, Map.of()), behavior.wire());
            assertEquals("each has invalid input(s): 'v' must be string, got boolean",
                    ParameterValidation.check("each", decl, Map.of("v", true)), behavior.wire());
        }
        assertEquals(7, ResolutionBehavior.values().length);
    }

    @Test
    void streamingInvocationLeavesAnOnMissingInputToTheHandler() throws Exception {
        StreamResult result = service.invokeStream("resolved", token("resolved", List.of("typed")),
                params("plain", "p", "mode_only", "m"), new InvokeOpts());
        List<StreamEvent> events = drain(result);
        assertEquals("completed", events.get(events.size() - 1).getType());
        assertEquals(1, resolvedCalls.get());

        result = service.invokeStream("resolved", token("resolved", List.of("typed")),
                params("mode_only", "m"), new InvokeOpts());
        assertInvalid(drain(result).get(0).getPayload(),
                "resolved is missing required input(s): plain");
        assertEquals(1, resolvedCalls.get());
    }

    // --- primitive types ---

    @Test
    void wrongTypesAreAllNamedInDeclarationOrder() throws Exception {
        Map<String, Object> response = invokeTyped(params(
                "o", List.of(1), "a", Map.of(), "b", "yes", "n", "1", "i", "5", "s", 5));
        assertInvalid(response, "typed has invalid input(s): "
                + "'s' must be string, got number; "
                + "'i' must be integer, got string; "
                + "'n' must be number, got string; "
                + "'b' must be boolean, got string; "
                + "'a' must be array, got object; "
                + "'o' must be object, got array");
        assertEquals(0, typedCalls.get());
    }

    @Test
    void everyPrimitiveTypeRejectsEveryOtherJsonType() throws Exception {
        Map<String, Object> jsonValues = new LinkedHashMap<>();
        jsonValues.put("string", "text");
        jsonValues.put("number", 1.5);
        jsonValues.put("boolean", true);
        jsonValues.put("array", List.of("x"));
        jsonValues.put("object", Map.of("k", "v"));
        Map<String, String> inputs = new LinkedHashMap<>();
        inputs.put("s", "string");
        inputs.put("i", "integer");
        inputs.put("n", "number");
        inputs.put("b", "boolean");
        inputs.put("a", "array");
        inputs.put("o", "object");

        for (Map.Entry<String, String> input : inputs.entrySet()) {
            for (Map.Entry<String, Object> value : jsonValues.entrySet()) {
                String declared = input.getValue();
                String received = value.getKey();
                // 1.5 is a number but not an integer; every other pair matches by name.
                boolean accepted = declared.equals(received);
                Map<String, Object> p = params("s", "x", "i", 1);
                p.put(input.getKey(), value.getValue());
                Map<String, Object> response = invokeTyped(p);
                if (accepted) {
                    assertEquals(true, response.get("success"), declared + " <- " + received);
                } else {
                    assertInvalid(response, "typed has invalid input(s): '" + input.getKey()
                            + "' must be " + declared + ", got " + received);
                }
            }
        }
    }

    @Test
    void integerAcceptsAnyIntegralNumber() throws Exception {
        List<Object> integral = List.of(
                5, 5L, (short) 5, (byte) 5, 5.0, 5.0f, 1e2, -0.0,
                new BigInteger("123456789012345678901234567890"),
                new BigDecimal("5.0"), new BigDecimal("1e2"), new BigDecimal("5"),
                new BigDecimal("0.0"), new AtomicInteger(5));
        for (Object value : integral) {
            Map<String, Object> response = invokeTyped(params("s", "x", "i", value));
            assertEquals(true, response.get("success"),
                    value.getClass().getSimpleName() + " " + value + ": " + response);
        }
    }

    @Test
    void integerRejectsFractionsAndNonFiniteNumbers() throws Exception {
        List<Object> notIntegral = List.of(
                1.5, 1.5f, new BigDecimal("1.5"), new BigDecimal("5.000000000000000000001"),
                Double.NaN, Double.POSITIVE_INFINITY);
        for (Object value : notIntegral) {
            assertInvalid(invokeTyped(params("s", "x", "i", value)),
                    "typed has invalid input(s): 'i' must be integer, got number");
        }
        assertEquals(0, typedCalls.get());
    }

    @Test
    void aBooleanIsNeverANumber() throws Exception {
        assertInvalid(invokeTyped(params("s", "x", "i", true)),
                "typed has invalid input(s): 'i' must be integer, got boolean");
        assertInvalid(invokeTyped(params("s", "x", "i", 1, "n", false)),
                "typed has invalid input(s): 'n' must be number, got boolean");
    }

    @Test
    void numberAcceptsEveryNumericRepresentation() throws Exception {
        for (Object value : List.of(1, 1L, 1.5, 1.5f, new BigDecimal("1.5"), BigInteger.TEN)) {
            Map<String, Object> response = invokeTyped(params("s", "x", "i", 1, "n", value));
            assertEquals(true, response.get("success"), value.getClass().getSimpleName());
        }
    }

    @Test
    void otherInMemoryRepresentationsAreMappedToAJsonType() throws Exception {
        // Collections are arrays, maps are objects, character sequences are strings.
        Map<String, Object> response = invokeTyped(params(
                "s", new StringBuilder("x"), "i", 1,
                "a", new java.util.HashSet<>(List.of(1)), "o", new HashMap<>(Map.of("k", 1))));
        assertEquals(true, response.get("success"), String.valueOf(response));

        assertInvalid(invokeTyped(params("s", "x", "i", 1, "a", new String[] {"x"}, "o", new int[] {1})),
                "typed has invalid input(s): 'o' must be object, got array");
    }

    @Test
    void jacksonTreeValuesAreRecognised() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        Map<String, Object> ok = params(
                "s", mapper.readTree("\"x\""), "i", mapper.readTree("5.0"),
                "n", mapper.readTree("1.5"), "b", mapper.readTree("true"),
                "a", mapper.readTree("[1]"), "o", mapper.readTree("{\"k\":1}"));
        assertEquals(true, invokeTyped(ok).get("success"));

        assertInvalid(invokeTyped(params("s", mapper.readTree("null"), "i", mapper.readTree("1"))),
                "typed is missing required input(s): s");
        assertInvalid(invokeTyped(params("s", mapper.readTree("7"), "i", mapper.readTree("1.5"))),
                "typed has invalid input(s): 's' must be string, got number; "
                        + "'i' must be integer, got number");
    }

    @Test
    void domainTypesAndUnknownTypeNamesAreNotChecked() throws Exception {
        // 'airport_code' is a domain type; 'String' is not the primitive 'string'.
        Map<String, Object> response = invokeTyped(params(
                "s", "x", "i", 1, "code", true, "upper", 12));
        assertEquals(true, response.get("success"), String.valueOf(response));
        assertEquals(1, typedCalls.get());
    }

    @Test
    void optionalInputsMayBeAbsentOrNull() throws Exception {
        assertEquals(true, invokeTyped(params("s", "x", "i", 1)).get("success"));
        assertEquals(true, invokeTyped(params(
                "s", "x", "i", 1, "n", null, "b", null, "a", null, "o", null)).get("success"));
    }

    @Test
    void undeclaredParametersReachTheHandler() throws Exception {
        Map<String, Object> response = invokeTyped(params(
                "s", "x", "i", 1, "extra", List.of(1, 2), "another", true));
        assertEquals(true, response.get("success"), String.valueOf(response));
        assertEquals(List.of(1, 2), lastTypedParams.get().get("extra"));
        assertEquals(true, lastTypedParams.get().get("another"));
    }

    // --- position in the pipeline ---

    @Test
    void delegationFailureIsReportedBeforeInvalidParameters() throws Exception {
        // A token for another capability: the caller learns that, not which
        // parameters are wrong.
        Map<String, Object> response = service.invoke("typed",
                token("defaulted", List.of("typed")), Map.of(), new InvokeOpts());
        assertEquals(Constants.FAILURE_PURPOSE_MISMATCH, failure(response).get("type"));
    }

    @Test
    void bindingEnforcementRunsBeforeParameterValidation() throws Exception {
        // 'flight' (required) and the 'quote_id' binding are both absent.
        Map<String, Object> response = service.invoke("bound",
                token("bound", List.of("typed")), Map.of(), new InvokeOpts());
        assertEquals(Constants.FAILURE_BINDING_MISSING, failure(response).get("type"));

        // With the binding supplied the missing input is reported.
        response = service.invoke("bound", token("bound", List.of("typed")),
                params("quote_id", Map.of("id", "q1")), new InvokeOpts());
        assertInvalid(response, "bound is missing required input(s): flight");
        assertEquals(0, boundCalls.get());
    }

    // --- a refused call has no effect ---

    @Test
    void anInvalidCallDoesNotReachAHandlerThatAsksForApproval() throws Exception {
        DelegationToken token = token("sensitive", List.of("typed"));
        Map<String, Object> control = service.invoke("sensitive", token,
                params("memo", "m", "amount", 5), new InvokeOpts());
        assertEquals(Constants.FAILURE_APPROVAL_REQUIRED, failure(control).get("type"));
        assertEquals(1, sensitiveCalls.get());

        Map<String, Object> response = service.invoke("sensitive", token,
                params("memo", 12345, "amount", 5), new InvokeOpts());
        assertInvalid(response, "sensitive has invalid input(s): 'memo' must be string, got number");
        assertFalse(failure(response).containsKey("approval_required"));
        assertEquals(1, sensitiveCalls.get(), "the handler must not run again");
    }

    @SuppressWarnings("unchecked")
    private String approvedGrant(DelegationToken token, Map<String, Object> parameters) throws Exception {
        Map<String, Object> first = service.invoke("sensitive", token, parameters, new InvokeOpts());
        Map<String, Object> approval = (Map<String, Object>) failure(first).get("approval_required");
        ApprovalGrant grant = service.issueApprovalGrant(
                (String) approval.get("approval_request_id"), "one_time",
                Map.of("subject", "approver", "root_principal", "approver"), null, null, null);
        return grant.getGrantId();
    }

    @Test
    void anInvalidContinuationDoesNotSpendTheGrant() throws Exception {
        DelegationToken token = token("sensitive", List.of("typed"));
        String grantId = approvedGrant(token, params("memo", "m", "amount", 5));

        InvokeOpts opts = new InvokeOpts();
        opts.setApprovalGrant(grantId);
        Map<String, Object> refused = service.invoke("sensitive", token,
                params("memo", 12345, "amount", 5), opts);
        assertInvalid(refused, "sensitive has invalid input(s): 'memo' must be string, got number");
        assertEquals(0, service.getStorage().getGrant(grantId).orElseThrow().getUseCount());

        InvokeOpts again = new InvokeOpts();
        again.setApprovalGrant(grantId);
        Map<String, Object> continued = service.invoke("sensitive", token,
                params("memo", "m", "amount", 5), again);
        assertEquals(true, continued.get("success"), String.valueOf(continued));
    }

    // --- streaming ---

    private static List<StreamEvent> drain(StreamResult result) throws Exception {
        List<StreamEvent> events = new ArrayList<>();
        while (true) {
            StreamEvent event = result.getEvents().poll(5, TimeUnit.SECONDS);
            assertNotNull(event, "timed out waiting for a stream event");
            if (StreamResult.DONE_TYPE.equals(event.getType())) return events;
            events.add(event);
        }
    }

    @Test
    void streamingInvocationIsCheckedTheSameWay() throws Exception {
        InvokeOpts opts = new InvokeOpts("ref-s", true, "task-s", null);
        StreamResult result = service.invokeStream("typed",
                token("typed", List.of("typed"), "task-s"), params("s", 5, "i", 1.5), opts);

        List<StreamEvent> events = drain(result);
        assertEquals(1, events.size());
        assertEquals("failed", events.get(0).getType());
        Map<String, Object> payload = events.get(0).getPayload();
        assertInvalid(payload, "typed has invalid input(s): 's' must be string, got number; "
                + "'i' must be integer, got number");
        assertEquals("ref-s", payload.get("client_reference_id"));
        assertEquals("task-s", payload.get("task_id"));
        assertEquals(0, typedCalls.get(), "the handler must not run");

        AuditEntry entry = auditEntry("typed", (String) payload.get("invocation_id"));
        assertFalse(entry.isSuccess());
        assertEquals(Constants.FAILURE_INVALID_PARAMETERS, entry.getFailureType());
    }

    @Test
    void streamingInvocationWithMissingInputIsRefused() throws Exception {
        StreamResult result = service.invokeStream("typed", token("typed", List.of("typed")),
                null, new InvokeOpts());
        List<StreamEvent> events = drain(result);
        assertEquals(1, events.size());
        assertInvalid(events.get(0).getPayload(), "typed is missing required input(s): s, i");
    }

    @Test
    void streamingInvocationWithValidParametersRuns() throws Exception {
        StreamResult result = service.invokeStream("typed", token("typed", List.of("typed")),
                params("s", "x", "i", 5.0), new InvokeOpts());
        List<StreamEvent> events = drain(result);
        assertEquals("completed", events.get(events.size() - 1).getType());
        assertEquals(1, typedCalls.get());
    }

    @Test
    void anInvalidStreamingContinuationDoesNotSpendTheGrant() throws Exception {
        DelegationToken token = token("sensitive", List.of("typed"));
        String grantId = approvedGrant(token, params("memo", "m", "amount", 5));

        InvokeOpts opts = new InvokeOpts();
        opts.setApprovalGrant(grantId);
        StreamResult result = service.invokeStream("sensitive", token,
                params("memo", "m", "amount", "five"), opts);
        List<StreamEvent> events = drain(result);
        assertInvalid(events.get(0).getPayload(),
                "sensitive has invalid input(s): 'amount' must be integer, got string");
        assertEquals(0, service.getStorage().getGrant(grantId).orElseThrow().getUseCount());
    }

    // --- composition ---

    @Test
    void aComposedCapabilityIsCheckedBeforeAnyChildStep() throws Exception {
        Map<String, Object> response = service.invoke("parent",
                token("parent", List.of("typed")), Map.of(), new InvokeOpts());
        assertInvalid(response, "parent is missing required input(s): in");
        assertEquals(0, childCalls.get());
    }

    @Test
    void eachChildStepIsCheckedAgainstTheChildDeclaration() throws Exception {
        // The parent's own input is valid; the step does not supply the
        // child's required input, so the child invocation is refused.
        Map<String, Object> response = service.invoke("parent",
                token("parent", List.of("typed")), params("in", "x"), new InvokeOpts());
        assertEquals(false, response.get("success"), String.valueOf(response));
        assertEquals(0, childCalls.get(), "the child handler must not run");

        List<AuditEntry> entries = service.getStorage().queryAuditEntries(
                new AuditFilters("child", null, null, null, null, null, null, 50));
        assertEquals(1, entries.size());
        assertEquals(Constants.FAILURE_INVALID_PARAMETERS, entries.get(0).getFailureType());
    }
}
