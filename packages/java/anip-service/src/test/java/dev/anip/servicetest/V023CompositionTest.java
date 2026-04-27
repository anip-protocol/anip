package dev.anip.servicetest;

import dev.anip.core.ANIPError;
import dev.anip.core.AuditPolicy;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.Composition;
import dev.anip.core.CompositionStep;
import dev.anip.core.FailurePolicy;
import dev.anip.core.SideEffect;
import dev.anip.service.V023;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/** v0.23 composition validator + executor tests. SPEC.md §4.6. */
class V023CompositionTest {

    private static CapabilityDeclaration atomic(String name) {
        return new CapabilityDeclaration(name, "d", "1.0",
                List.<CapabilityInput>of(),
                new CapabilityOutput("object", List.of()),
                new SideEffect("read", "not_applicable"),
                List.of("scope"), null, null, List.of("sync"));
    }

    private static CapabilityDeclaration composed(String name, Composition comp) {
        return new CapabilityDeclaration(name, "d", "1.0",
                List.<CapabilityInput>of(),
                new CapabilityOutput("object", List.of()),
                new SideEffect("read", "not_applicable"),
                List.of("scope"), null, null, List.of("sync"))
                .setKind("composed").setComposition(comp);
    }

    private static Map<String, Map<String, String>> mapping(String stepId, Map<String, String> m) {
        Map<String, Map<String, String>> r = new LinkedHashMap<>();
        r.put(stepId, m);
        return r;
    }

    @Test
    void rejectsMissingComposition() {
        CapabilityDeclaration d = atomic("p").setKind("composed");
        Map<String, CapabilityDeclaration> reg = Map.of("p", d);
        var ex = assertThrows(V023.CompositionValidationError.class,
                () -> V023.validateComposition("p", d, reg));
        assertTrue(ex.getMessage().contains("composition is missing"));
    }

    @Test
    void rejectsUnknownAuthorityBoundary() {
        Composition c = new Composition("cross_service", List.of(new CompositionStep("a", "x")),
                Map.of(), Map.of(), new FailurePolicy(), new AuditPolicy(true, true));
        CapabilityDeclaration d = composed("p", c);
        var ex = assertThrows(V023.CompositionValidationError.class,
                () -> V023.validateComposition("p", d, Map.of("p", d, "x", atomic("x"))));
        assertTrue(ex.getMessage().contains("unsupported_authority_boundary"));
    }

    @Test
    void rejectsSelfReference() {
        Composition c = new Composition("same_service",
                List.of(new CompositionStep("a", "p")),
                Map.of(), Map.of(), new FailurePolicy(), new AuditPolicy(true, true));
        CapabilityDeclaration d = composed("p", c);
        var ex = assertThrows(V023.CompositionValidationError.class,
                () -> V023.validateComposition("p", d, Map.of("p", d)));
        assertTrue(ex.getMessage().contains("self-references"));
    }

    @Test
    void rejectsUnknownChild() {
        Composition c = new Composition("same_service",
                List.of(new CompositionStep("a", "missing")),
                Map.of(), Map.of(), new FailurePolicy(), new AuditPolicy(true, true));
        CapabilityDeclaration d = composed("p", c);
        var ex = assertThrows(V023.CompositionValidationError.class,
                () -> V023.validateComposition("p", d, Map.of("p", d)));
        assertTrue(ex.getMessage().contains("unknown_capability"));
    }

    @Test
    void rejectsComposedChild() {
        CapabilityDeclaration child = composed("c", new Composition("same_service",
                List.of(new CompositionStep("aa", "x")),
                Map.of(), Map.of(), new FailurePolicy(), new AuditPolicy(true, true)));
        Composition c = new Composition("same_service",
                List.of(new CompositionStep("a", "c")),
                Map.of(), Map.of(), new FailurePolicy(), new AuditPolicy(true, true));
        CapabilityDeclaration d = composed("p", c);
        var ex = assertThrows(V023.CompositionValidationError.class,
                () -> V023.validateComposition("p", d,
                        Map.of("p", d, "c", child, "x", atomic("x"))));
        assertTrue(ex.getMessage().contains("composed capabilities may only call kind='atomic'"));
    }

    @Test
    void rejectsForwardReferenceInInputMapping() {
        Composition c = new Composition("same_service",
                List.of(new CompositionStep("a", "x"), new CompositionStep("b", "y")),
                mapping("a", Map.of("v", "$.steps.b.output.q")),
                Map.of(), new FailurePolicy(), new AuditPolicy(true, true));
        CapabilityDeclaration d = composed("p", c);
        var ex = assertThrows(V023.CompositionValidationError.class,
                () -> V023.validateComposition("p", d,
                        Map.of("p", d, "x", atomic("x"), "y", atomic("y"))));
        assertTrue(ex.getMessage().contains("forward-references"));
    }

    @Test
    void linearCompositionExecutes() {
        Composition c = new Composition("same_service",
                List.of(new CompositionStep("first", "x"), new CompositionStep("second", "y")),
                Map.of("first", Map.of("p", "$.input.in"),
                       "second", Map.of("p", "$.steps.first.output.out")),
                Map.of("answer", "$.steps.second.output.out"),
                new FailurePolicy(), new AuditPolicy(true, true));
        CapabilityDeclaration d = composed("p", c);
        Map<String, Object> input = Map.of("in", "hello");
        Map<String, Object> result = V023.executeComposition("p", d, input,
                (cap, params) -> Map.of("success", true,
                        "result", Map.of("out", "from-" + cap + ":" + params.get("p"))));
        assertEquals("from-y:from-x:hello", result.get("answer"));
    }

    @Test
    void emptyResultClarifyRaisesAnipError() {
        Composition c = new Composition("same_service",
                List.of(new CompositionStep("sel", "x").setEmptyResultSource(true).setEmptyResultPath("rows")),
                Map.of(),
                Map.of("rows", "$.steps.sel.output.rows"),
                new FailurePolicy(), new AuditPolicy(true, true))
                .setEmptyResultPolicy("clarify");
        CapabilityDeclaration d = composed("p", c);
        ANIPError err = assertThrows(ANIPError.class,
                () -> V023.executeComposition("p", d, Map.of(),
                        (cap, params) -> Map.of("success", true,
                                "result", Map.of("rows", List.of()))));
        assertEquals("composition_empty_result_clarification_required", err.getErrorType());
    }

    @Test
    void failParentCollapsesToCompositionChildFailed() {
        Composition c = new Composition("same_service",
                List.of(new CompositionStep("a", "x")),
                Map.of(), Map.of(), new FailurePolicy(), new AuditPolicy(true, true));
        CapabilityDeclaration d = composed("p", c);
        ANIPError err = assertThrows(ANIPError.class,
                () -> V023.executeComposition("p", d, Map.of(),
                        (cap, params) -> Map.of("success", false,
                                "failure", Map.of("type", "internal_error", "detail", "boom"))));
        assertEquals("composition_child_failed", err.getErrorType());
        // child failure type captured in detail for diagnostics.
        assertTrue(err.getDetail().contains("internal_error"));
    }

    @Test
    void propagatePassesThroughChildFailureType() {
        FailurePolicy policy = new FailurePolicy("propagate", "propagate", "propagate", "propagate");
        Composition c = new Composition("same_service",
                List.of(new CompositionStep("a", "x")),
                Map.of(), Map.of(), policy, new AuditPolicy(true, true));
        CapabilityDeclaration d = composed("p", c);
        ANIPError err = assertThrows(ANIPError.class,
                () -> V023.executeComposition("p", d, Map.of(),
                        (cap, params) -> Map.of("success", false,
                                "failure", Map.of("type", "scope_insufficient", "detail", "x"))));
        assertEquals("scope_insufficient", err.getErrorType());
    }

    @Test
    void canonicalJsonStableAcrossKeyOrder() {
        Map<String, Object> a = new LinkedHashMap<>();
        a.put("z", 1); a.put("a", 2);
        Map<String, Object> b = new HashMap<>();
        b.put("a", 2); b.put("z", 1);
        assertEquals(V023.canonicalJson(a), V023.canonicalJson(b));
        // Recursive sort.
        Map<String, Object> nested = Map.of("outer", Map.of("z", 1, "a", 2));
        String json = V023.canonicalJson(nested);
        assertTrue(json.indexOf("\"a\":2") < json.indexOf("\"z\":1"));
    }

    @Test
    void sha256DigestPrefixedSha256Hex() {
        String d = V023.sha256Digest(Map.of("a", 1));
        assertTrue(d.startsWith("sha256:"));
        assertEquals(7 + 64, d.length());
    }
}
