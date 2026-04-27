package dev.anip.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.module.paramnames.ParameterNamesModule;

import dev.anip.core.ANIPError;
import dev.anip.core.ApprovalGrant;
import dev.anip.core.ApprovalRequest;
import dev.anip.core.ApprovalRequiredMetadata;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.Composition;
import dev.anip.core.CompositionStep;
import dev.anip.core.Constants;
import dev.anip.core.FailurePolicy;
import dev.anip.core.GrantPolicy;
import dev.anip.crypto.JwsSigner;
import dev.anip.crypto.KeyManager;
import dev.anip.server.ApprovalDecisionResult;
import dev.anip.server.Storage;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * v0.23 — Capability composition + approval grants runtime helpers.
 *
 * <p>Translates the canonical {@code anip_service.v023} (Python) and
 * {@code packages/go/service/v023.go} primitives:</p>
 * <ul>
 *   <li>composition validation (registration time)</li>
 *   <li>composition execution (sequential steps + empty/failure policies)</li>
 *   <li>SHA-256 digests over canonical JSON</li>
 *   <li>approval grant signing/verification (detached JWS over canonical
 *       grant payload, byte-for-byte identical to the other runtimes)</li>
 *   <li>continuation grant validation (Phase A read-side)</li>
 *   <li>ApprovalRequest materialization (Phase 7.1)</li>
 * </ul>
 *
 * <p>The {@code ANIPService} wires these into the invoke pipeline.</p>
 */
public final class V023 {

    private V023() {}

    /** ObjectMapper used only for converting POJOs to a JSON tree we can canonicalise. */
    private static final ObjectMapper MAPPER = JsonMapper.builder()
            .addModule(new ParameterNamesModule())
            .propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
            .configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false)
            .configure(SerializationFeature.WRITE_NULL_MAP_VALUES, true)
            .build();

    private static final SecureRandom RANDOM = new SecureRandom();

    private static final Pattern JSONPATH_INPUT =
            Pattern.compile("^\\$\\.input(?:\\.[A-Za-z_][A-Za-z0-9_]*)+$");
    private static final Pattern JSONPATH_STEP =
            Pattern.compile("^\\$\\.steps\\.([A-Za-z_][A-Za-z0-9_-]*)\\.output(?:\\.[A-Za-z_][A-Za-z0-9_]*)+$");

    // -----------------------------------------------------------------------
    // ID + time helpers
    // -----------------------------------------------------------------------

    public static String newApprovalRequestId() {
        return "apr_" + randomHex(6);
    }

    public static String newGrantId() {
        return "grant_" + randomHex(6);
    }

    private static String randomHex(int bytes) {
        byte[] b = new byte[bytes];
        RANDOM.nextBytes(b);
        StringBuilder sb = new StringBuilder(bytes * 2);
        for (byte v : b) {
            sb.append(String.format("%02x", v & 0xff));
        }
        return sb.toString();
    }

    public static String utcNowIso() {
        return DateTimeFormatter.ISO_INSTANT.format(Instant.now());
    }

    public static String utcInIso(int seconds) {
        return DateTimeFormatter.ISO_INSTANT.format(Instant.now().plus(Duration.ofSeconds(seconds)));
    }

    // -----------------------------------------------------------------------
    // Canonical JSON + SHA-256 digest
    // -----------------------------------------------------------------------

    /**
     * Serializes a value with recursively sorted keys, no whitespace. Matches
     * Python's {@code json.dumps(value, sort_keys=True, separators=(",", ":"))}
     * byte-for-byte and TS / Go canonicalJson — load-bearing for cross-runtime
     * grant verification.
     */
    public static String canonicalJson(Object value) {
        Object normalised;
        try {
            normalised = MAPPER.readValue(MAPPER.writeValueAsString(value), Object.class);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("canonicalJson normalize failed", e);
        }
        StringBuilder sb = new StringBuilder();
        canonicalEncode(sb, normalised);
        return sb.toString();
    }

    @SuppressWarnings("unchecked")
    private static void canonicalEncode(StringBuilder sb, Object v) {
        if (v == null) {
            sb.append("null");
            return;
        }
        if (v instanceof Boolean b) {
            sb.append(b ? "true" : "false");
            return;
        }
        if (v instanceof Number) {
            // Matches Jackson's default numeric encoding for double/int.
            sb.append(numberToCanonical((Number) v));
            return;
        }
        if (v instanceof CharSequence cs) {
            try {
                sb.append(MAPPER.writeValueAsString(cs.toString()));
            } catch (JsonProcessingException e) {
                throw new IllegalStateException(e);
            }
            return;
        }
        if (v instanceof List<?> list) {
            sb.append('[');
            boolean first = true;
            for (Object item : list) {
                if (!first) sb.append(',');
                canonicalEncode(sb, item);
                first = false;
            }
            sb.append(']');
            return;
        }
        if (v instanceof Map<?, ?> map) {
            // Sort keys lexicographically.
            TreeMap<String, Object> sorted = new TreeMap<>();
            for (Map.Entry<?, ?> e : map.entrySet()) {
                sorted.put(String.valueOf(e.getKey()), e.getValue());
            }
            sb.append('{');
            boolean first = true;
            for (Map.Entry<String, Object> e : sorted.entrySet()) {
                if (!first) sb.append(',');
                try {
                    sb.append(MAPPER.writeValueAsString(e.getKey()));
                } catch (JsonProcessingException ex) {
                    throw new IllegalStateException(ex);
                }
                sb.append(':');
                canonicalEncode(sb, e.getValue());
                first = true ? false : false;
                first = false;
            }
            sb.append('}');
            return;
        }
        // Fallback: roundtrip through Jackson.
        try {
            sb.append(MAPPER.writeValueAsString(v));
        } catch (JsonProcessingException e) {
            throw new IllegalStateException(e);
        }
    }

    private static String numberToCanonical(Number n) {
        if (n instanceof Integer || n instanceof Long || n instanceof Short || n instanceof Byte) {
            return n.toString();
        }
        if (n instanceof Double d) {
            // Match Python's behavior of integer-valued floats serializing as integers.
            if (d == Math.floor(d) && !Double.isInfinite(d)) {
                long asLong = d.longValue();
                if ((double) asLong == d) {
                    return Long.toString(asLong) + ".0";
                }
            }
            return d.toString();
        }
        if (n instanceof Float f) {
            return Float.toString(f);
        }
        return n.toString();
    }

    /** SHA-256 over canonical JSON, returns "sha256:<hex>". */
    public static String sha256Digest(Object value) {
        byte[] payload = canonicalJson(value).getBytes(StandardCharsets.UTF_8);
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(payload);
            StringBuilder hex = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                hex.append(String.format("%02x", b & 0xff));
            }
            return "sha256:" + hex;
        } catch (Exception e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    // -----------------------------------------------------------------------
    // Composition validation
    // -----------------------------------------------------------------------

    /** Thrown when a composed capability declaration violates a v0.23 invariant. */
    public static final class CompositionValidationError extends RuntimeException {
        public CompositionValidationError(String message) { super(message); }
    }

    /**
     * Enforces SPEC.md §4.6 invariants on a composed capability declaration.
     * No-op when {@code decl.kind != "composed"}.
     */
    public static void validateComposition(String parentName, CapabilityDeclaration decl,
                                            Map<String, CapabilityDeclaration> registry) {
        if (!"composed".equals(decl.getKind())) {
            return;
        }
        Composition comp = decl.getComposition();
        if (comp == null) {
            throw err("composition_invalid_step: capability '" + parentName
                    + "' declares kind='composed' but composition is missing");
        }
        if (!"same_service".equals(comp.getAuthorityBoundary())) {
            throw err("composition_unsupported_authority_boundary: '"
                    + comp.getAuthorityBoundary() + "' is reserved in v0.23");
        }
        if (comp.getSteps() == null || comp.getSteps().isEmpty()) {
            throw err("composition_invalid_step: composition has no steps");
        }

        // Step IDs must be unique.
        Map<String, Integer> stepIndex = new HashMap<>();
        for (int i = 0; i < comp.getSteps().size(); i++) {
            CompositionStep s = comp.getSteps().get(i);
            if (stepIndex.containsKey(s.getId())) {
                throw err("composition_invalid_step: duplicate step ids");
            }
            stepIndex.put(s.getId(), i);
        }

        // At most one empty_result_source.
        CompositionStep sourceStep = null;
        for (CompositionStep s : comp.getSteps()) {
            if (s.isEmptyResultSource()) {
                if (sourceStep != null) {
                    throw err("composition_invalid_step: at most one step may have empty_result_source=true");
                }
                sourceStep = s;
            }
        }

        // Step capabilities must resolve and be kind=atomic. No self-reference.
        for (CompositionStep step : comp.getSteps()) {
            if (parentName.equals(step.getCapability())) {
                throw err("composition_invalid_step: step '" + step.getId()
                        + "' self-references parent capability");
            }
            CapabilityDeclaration target = registry.get(step.getCapability());
            if (target == null) {
                throw err("composition_unknown_capability: step '" + step.getId()
                        + "' references unknown capability '" + step.getCapability() + "'");
            }
            String kind = target.getKind() == null || target.getKind().isEmpty() ? "atomic" : target.getKind();
            if (!"atomic".equals(kind)) {
                throw err("composition_invalid_step: step '" + step.getId()
                        + "' references '" + step.getCapability() + "' which is kind='"
                        + kind + "'; composed capabilities may only call kind='atomic' steps in v0.23");
            }
        }

        // input_mapping references must resolve and be forward-only.
        if (comp.getInputMapping() != null) {
            for (Map.Entry<String, Map<String, String>> e : comp.getInputMapping().entrySet()) {
                String stepKey = e.getKey();
                Integer stepPos = stepIndex.get(stepKey);
                if (stepPos == null) {
                    throw err("composition_invalid_step: input_mapping key '" + stepKey
                            + "' is not a declared step id");
                }
                for (Map.Entry<String, String> param : e.getValue().entrySet()) {
                    String ref = parseStepRef(param.getValue());
                    if (ref == null) continue;
                    Integer refPos = stepIndex.get(ref);
                    if (refPos == null) {
                        throw err("composition_invalid_step: input_mapping[" + stepKey + "]." + param.getKey()
                                + " references unknown step '" + ref + "'");
                    }
                    if (refPos >= stepPos) {
                        throw err("composition_invalid_step: input_mapping[" + stepKey + "]." + param.getKey()
                                + " forward-references '" + ref + "' (forward-only references required)");
                    }
                }
            }
        }

        // output_mapping references must resolve.
        if (comp.getOutputMapping() != null) {
            for (Map.Entry<String, String> e : comp.getOutputMapping().entrySet()) {
                String ref = parseStepRef(e.getValue());
                if (ref == null) continue;
                if (!stepIndex.containsKey(ref)) {
                    throw err("composition_invalid_step: output_mapping['" + e.getKey()
                            + "'] references unknown step '" + ref + "'");
                }
            }
        }

        // empty_result_source step requires composition-level empty_result_policy.
        if (sourceStep != null && (comp.getEmptyResultPolicy() == null || comp.getEmptyResultPolicy().isEmpty())) {
            throw err("composition_invalid_step: step has empty_result_source=true but composition has no empty_result_policy");
        }

        String policy = comp.getEmptyResultPolicy();
        if ("return_success_no_results".equals(policy)) {
            if (comp.getEmptyResultOutput() == null) {
                throw err("composition_invalid_step: empty_result_policy='return_success_no_results' requires empty_result_output");
            }
            if (sourceStep == null) {
                throw err("composition_invalid_step: empty_result_output requires a step with empty_result_source=true");
            }
            for (Map.Entry<String, Object> e : comp.getEmptyResultOutput().entrySet()) {
                if (e.getValue() instanceof String s && s.startsWith("$")) {
                    String ref = parseStepRef(s);
                    if (ref != null && !ref.equals(sourceStep.getId())) {
                        throw err("composition_invalid_step: empty_result_output['" + e.getKey()
                                + "'] references step '" + ref + "' but only the empty_result_source step '"
                                + sourceStep.getId() + "' (or $.input.*) is allowed");
                    }
                }
            }
        } else if (("clarify".equals(policy) || "deny".equals(policy)) && comp.getEmptyResultOutput() != null) {
            throw err("composition_invalid_step: empty_result_output is forbidden when empty_result_policy='"
                    + policy + "'");
        }
    }

    /** Returns the step id referenced by a JSONPath, or null for $.input.*. */
    private static String parseStepRef(String path) {
        if (JSONPATH_INPUT.matcher(path).matches()) {
            return null;
        }
        Matcher m = JSONPATH_STEP.matcher(path);
        if (!m.matches()) {
            throw err("composition_invalid_step: malformed JSONPath '" + path
                    + "' (must be $.input.* or $.steps.<id>.output.*)");
        }
        return m.group(1);
    }

    private static CompositionValidationError err(String msg) {
        return new CompositionValidationError(msg);
    }

    // -----------------------------------------------------------------------
    // Composition execution
    // -----------------------------------------------------------------------

    /** Invokes a child capability with the parent's authority/audit lineage. */
    @FunctionalInterface
    public interface InvokeStepFunc {
        Map<String, Object> invoke(String capability, Map<String, Object> params);
    }

    /**
     * Runs a composed capability's steps and returns the parent response body.
     * Throws {@link ANIPError} on policy-driven failures.
     */
    public static Map<String, Object> executeComposition(String parentName,
                                                          CapabilityDeclaration decl,
                                                          Map<String, Object> parentInput,
                                                          InvokeStepFunc invokeStep) {
        Composition comp = decl.getComposition();
        if (comp == null) {
            throw new IllegalStateException("capability '" + parentName + "' has no composition");
        }
        CompositionStep sourceStep = null;
        for (CompositionStep s : comp.getSteps()) {
            if (s.isEmptyResultSource()) { sourceStep = s; break; }
        }

        Map<String, Map<String, Object>> stepOutputs = new HashMap<>();
        for (CompositionStep step : comp.getSteps()) {
            Map<String, String> mapping = comp.getInputMapping() != null
                    ? comp.getInputMapping().getOrDefault(step.getId(), Map.of())
                    : Map.of();
            Map<String, Object> stepInput = new LinkedHashMap<>();
            for (Map.Entry<String, String> e : mapping.entrySet()) {
                stepInput.put(e.getKey(), tryResolveJsonPath(e.getValue(), parentInput, stepOutputs));
            }

            Map<String, Object> result = invokeStep.invoke(step.getCapability(), stepInput);
            boolean success = Boolean.TRUE.equals(result.get("success"));
            if (!success) {
                @SuppressWarnings("unchecked")
                Map<String, Object> failure = (Map<String, Object>) result.getOrDefault("failure", Map.of());
                String failureType = (String) failure.getOrDefault("type", "unknown");
                String detail = (String) failure.getOrDefault("detail", "child step failed");
                String outcome = failureOutcomeFor(failureType, comp.getFailurePolicy());
                if ("fail_parent".equals(outcome)) {
                    // Collapse to a uniform composition_child_failed; capture child's failure type in detail.
                    throw new ANIPError(Constants.FAILURE_COMPOSITION_CHILD_FAILED,
                            "child step '" + step.getId() + "' (" + step.getCapability()
                                    + ") failed with " + failureType + ": " + detail)
                            .withResolution("contact_service_owner");
                }
                ANIPError propagated = new ANIPError(failureType, detail);
                @SuppressWarnings("unchecked")
                Map<String, Object> appReq = (Map<String, Object>) failure.get("approval_required");
                if (appReq != null) {
                    ApprovalRequiredMetadata meta = approvalMetadataFromMap(appReq);
                    if (meta != null) propagated.withApprovalRequired(meta);
                }
                throw propagated;
            }

            @SuppressWarnings("unchecked")
            Map<String, Object> stepResult = (Map<String, Object>) result.get("result");
            if (stepResult == null) stepResult = Map.of();
            stepOutputs.put(step.getId(), stepResult);

            if (sourceStep != null && step.getId().equals(sourceStep.getId())
                    && isEmptyForStep(step, stepResult)) {
                return buildEmptyResultResponse(comp, parentInput, stepResult);
            }
        }
        return buildOutput(comp.getOutputMapping(), parentInput, stepOutputs);
    }

    private static String failureOutcomeFor(String failureType, FailurePolicy policy) {
        if (policy == null) policy = new FailurePolicy();
        if ("approval_required".equals(failureType)) return policy.getChildApprovalRequired();
        if ("scope_insufficient".equals(failureType) || "denied".equals(failureType)
                || "non_delegable_action".equals(failureType)) return policy.getChildDenial();
        if ("binding_missing".equals(failureType) || "binding_stale".equals(failureType)
                || "control_requirement_unsatisfied".equals(failureType)
                || "purpose_mismatch".equals(failureType)
                || "invalid_parameters".equals(failureType)) return policy.getChildClarification();
        return policy.getChildError();
    }

    private static Object tryResolveJsonPath(String path, Map<String, Object> parentInput,
                                              Map<String, Map<String, Object>> stepOutputs) {
        try {
            return resolveJsonPath(path, parentInput, stepOutputs);
        } catch (RuntimeException e) {
            return null;
        }
    }

    @SuppressWarnings("unchecked")
    private static Object resolveJsonPath(String path, Map<String, Object> parentInput,
                                           Map<String, Map<String, Object>> stepOutputs) {
        if (JSONPATH_INPUT.matcher(path).matches()) {
            String[] parts = path.split("\\.");
            Object cur = parentInput;
            for (int i = 2; i < parts.length; i++) {
                if (!(cur instanceof Map)) throw new RuntimeException("not an object at " + path);
                cur = ((Map<String, Object>) cur).get(parts[i]);
                if (cur == null) throw new RuntimeException("missing key '" + parts[i] + "' at " + path);
            }
            return cur;
        }
        Matcher m = JSONPATH_STEP.matcher(path);
        if (!m.matches()) throw new RuntimeException("malformed JSONPath " + path);
        String stepId = m.group(1);
        Map<String, Object> out = stepOutputs.get(stepId);
        if (out == null) throw new RuntimeException("step '" + stepId + "' has no output");
        String[] parts = path.split("\\.");
        Object cur = out;
        for (int i = 4; i < parts.length; i++) {
            if (!(cur instanceof Map)) throw new RuntimeException("not an object at " + path);
            cur = ((Map<String, Object>) cur).get(parts[i]);
            if (cur == null) throw new RuntimeException("missing key '" + parts[i] + "' at " + path);
        }
        return cur;
    }

    @SuppressWarnings("unchecked")
    private static boolean isEmptyValue(Object v) {
        if (v == null) return true;
        if (v instanceof List<?> l) return l.isEmpty();
        if (v instanceof Map<?, ?> m) return m.isEmpty();
        if (v instanceof CharSequence cs) return cs.length() == 0;
        return false;
    }

    @SuppressWarnings("unchecked")
    private static boolean isEmptyForStep(CompositionStep step, Map<String, Object> output) {
        if (output == null || output.isEmpty()) return true;
        if (step.getEmptyResultPath() != null && !step.getEmptyResultPath().isEmpty()) {
            String[] keys = step.getEmptyResultPath().split("\\.");
            Object cur = output;
            for (String k : keys) {
                if (k.isEmpty() || "$".equals(k)) continue;
                if (!(cur instanceof Map)) return true;
                cur = ((Map<String, Object>) cur).get(k);
                if (cur == null) return true;
            }
            return isEmptyValue(cur);
        }
        // Heuristic: any list-typed value is treated as the primary collection.
        for (Object v : output.values()) {
            if (v instanceof List<?> l) return l.isEmpty();
        }
        for (Object v : output.values()) {
            if (!isEmptyValue(v)) return false;
        }
        return true;
    }

    private static Map<String, Object> buildOutput(Map<String, String> mapping,
                                                    Map<String, Object> parentInput,
                                                    Map<String, Map<String, Object>> stepOutputs) {
        Map<String, Object> out = new LinkedHashMap<>();
        if (mapping == null) return out;
        for (Map.Entry<String, String> e : mapping.entrySet()) {
            out.put(e.getKey(), tryResolveJsonPath(e.getValue(), parentInput, stepOutputs));
        }
        return out;
    }

    private static Map<String, Object> buildEmptyResultResponse(Composition comp,
                                                                  Map<String, Object> parentInput,
                                                                  Map<String, Object> sourceOutput) {
        if ("clarify".equals(comp.getEmptyResultPolicy())) {
            throw new ANIPError("composition_empty_result_clarification_required",
                    "selection step returned no results; clarification required");
        }
        if ("deny".equals(comp.getEmptyResultPolicy())) {
            throw new ANIPError("composition_empty_result_denied",
                    "selection step returned no results; policy denies an empty answer");
        }
        Map<String, Object> out = new LinkedHashMap<>();
        Map<String, Object> emptyOut = comp.getEmptyResultOutput();
        if (emptyOut == null) return out;
        for (Map.Entry<String, Object> e : emptyOut.entrySet()) {
            Object v = e.getValue();
            if (v instanceof String s && s.startsWith("$")) {
                out.put(e.getKey(), tryResolveEmptyRef(s, parentInput, sourceOutput));
            } else {
                out.put(e.getKey(), v);
            }
        }
        return out;
    }

    private static Object tryResolveEmptyRef(String path, Map<String, Object> parentInput,
                                              Map<String, Object> sourceOutput) {
        try {
            if (JSONPATH_INPUT.matcher(path).matches()) {
                Map<String, Map<String, Object>> empty = Map.of();
                return resolveJsonPath(path, parentInput, empty);
            }
            Matcher m = JSONPATH_STEP.matcher(path);
            if (!m.matches()) return null;
            String[] parts = path.split("\\.");
            Object cur = sourceOutput;
            for (int i = 4; i < parts.length; i++) {
                if (!(cur instanceof Map)) return null;
                cur = ((Map<?, ?>) cur).get(parts[i]);
                if (cur == null) return null;
            }
            return cur;
        } catch (RuntimeException e) {
            return null;
        }
    }

    // -----------------------------------------------------------------------
    // Approval grant signing + verification
    // -----------------------------------------------------------------------

    /**
     * Detached JWS signature over the canonical JSON of the grant excluding
     * {@code signature} and {@code use_count}. v0.23 §4.8.
     */
    public static String signGrant(KeyManager km, ApprovalGrant grant) throws Exception {
        byte[] payload = grantSigningPayload(grant);
        return JwsSigner.signDetachedJws(km, payload);
    }

    /** Returns true if the grant's signature is valid for the canonical payload. */
    public static boolean verifyGrantSignature(KeyManager km, ApprovalGrant grant) {
        try {
            byte[] payload = grantSigningPayload(grant);
            JwsSigner.verifyDetachedJws(km, payload, grant.getSignature());
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @SuppressWarnings("unchecked")
    private static byte[] grantSigningPayload(ApprovalGrant grant) {
        Object tree;
        try {
            tree = MAPPER.readValue(MAPPER.writeValueAsString(grant), Object.class);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("grant serialize failed", e);
        }
        if (tree instanceof Map<?, ?> raw) {
            Map<String, Object> m = new LinkedHashMap<>();
            for (Map.Entry<?, ?> e : raw.entrySet()) {
                String k = String.valueOf(e.getKey());
                if ("signature".equals(k) || "use_count".equals(k)) continue;
                m.put(k, e.getValue());
            }
            return canonicalJson(m).getBytes(StandardCharsets.UTF_8);
        }
        return canonicalJson(tree).getBytes(StandardCharsets.UTF_8);
    }

    /** SPEC.md §4.8: every grant scope element must appear in the token's scope. */
    public static boolean grantScopeSubsetOfToken(List<String> grantScope, List<String> tokenScope) {
        Set<String> tokenSet = new HashSet<>(tokenScope);
        for (String s : grantScope) {
            if (!tokenSet.contains(s)) return false;
        }
        return true;
    }

    // -----------------------------------------------------------------------
    // ApprovalRequest materialization (Phase 7.1)
    // -----------------------------------------------------------------------

    public record ApprovalMaterialization(ApprovalRequiredMetadata metadata, ApprovalRequest request) {}

    /**
     * Persists a fresh ApprovalRequest and returns the metadata + the persisted
     * request. Storage failures propagate; the caller maps to service_unavailable
     * per SPEC.md §4.7.
     */
    public static ApprovalMaterialization materializeApprovalRequest(
            Storage storage,
            CapabilityDeclaration decl,
            String parentInvocationId,
            Map<String, Object> requester,
            Map<String, Object> parameters,
            Map<String, Object> preview,
            GrantPolicy serviceDefaultGrantPolicy) throws Exception {
        GrantPolicy gp = decl.getGrantPolicy();
        if (gp == null) gp = serviceDefaultGrantPolicy;
        if (gp == null) {
            throw new IllegalStateException("capability '" + decl.getName()
                    + "' raised approval_required but has no grant_policy declared and no service-level default exists");
        }
        String id = newApprovalRequestId();
        String previewDigest = sha256Digest(preview);
        String paramsDigest = sha256Digest(parameters);
        String createdAt = utcNowIso();
        String expiresAt = utcInIso(gp.getExpiresInSeconds());
        List<String> scope = decl.getMinimumScope() != null
                ? new ArrayList<>(decl.getMinimumScope()) : List.of();
        ApprovalRequest req = new ApprovalRequest(
                id, decl.getName(), scope, requester, parentInvocationId,
                preview, previewDigest, parameters, paramsDigest, gp,
                ApprovalRequest.STATUS_PENDING, null, null, createdAt, expiresAt);
        storage.storeApprovalRequest(req);
        ApprovalRequiredMetadata meta = new ApprovalRequiredMetadata(
                id, previewDigest, paramsDigest, gp);
        return new ApprovalMaterialization(meta, req);
    }

    /** Best-effort rebuild of an ApprovalRequiredMetadata from a JSON-shaped map. */
    @SuppressWarnings("unchecked")
    public static ApprovalRequiredMetadata approvalMetadataFromMap(Map<String, Object> m) {
        if (m == null) return null;
        try {
            String id = (String) m.get("approval_request_id");
            if (id == null || id.isEmpty()) return null;
            String previewDigest = (String) m.get("preview_digest");
            String paramsDigest = (String) m.get("requested_parameters_digest");
            GrantPolicy gp = null;
            Object gpRaw = m.get("grant_policy");
            if (gpRaw instanceof Map<?, ?> gpMap) {
                Object allowed = gpMap.get("allowed_grant_types");
                Object def = gpMap.get("default_grant_type");
                Object exp = gpMap.get("expires_in_seconds");
                Object mu = gpMap.get("max_uses");
                if (allowed instanceof List<?> allowedList && def instanceof String defStr
                        && exp instanceof Number expN && mu instanceof Number muN) {
                    List<String> a = new ArrayList<>();
                    for (Object o : allowedList) a.add(String.valueOf(o));
                    gp = new GrantPolicy(a, defStr, expN.intValue(), muN.intValue());
                }
            }
            return new ApprovalRequiredMetadata(id, previewDigest, paramsDigest, gp);
        } catch (Exception e) {
            return null;
        }
    }

    // -----------------------------------------------------------------------
    // Continuation grant validation (Phase A read-side)
    // -----------------------------------------------------------------------

    /** Either the grant on success or a non-null failure_type on rejection. */
    public record ContinuationValidation(ApprovalGrant grant, String failureType) {
        public static ContinuationValidation ok(ApprovalGrant g) { return new ContinuationValidation(g, null); }
        public static ContinuationValidation fail(String reason) { return new ContinuationValidation(null, reason); }
    }

    /**
     * Validates a continuation grant supplied with an invoke (read-side, Phase A).
     * Atomic reservation is the caller's responsibility — see
     * {@link Storage#tryReserveGrant} for Phase B.
     *
     * <p>Per SPEC.md §4.8, {@code tokenSessionId} for session_bound grants MUST
     * come from the signed delegation token, never from caller-supplied input.</p>
     */
    public static ContinuationValidation validateContinuationGrant(
            Storage storage, KeyManager km,
            String grantId, String capability,
            Map<String, Object> parameters,
            List<String> tokenScope, String tokenSessionId,
            String nowIso) throws Exception {
        Optional<ApprovalGrant> opt = storage.getGrant(grantId);
        if (opt.isEmpty()) return ContinuationValidation.fail(Constants.FAILURE_GRANT_NOT_FOUND);
        ApprovalGrant grant = opt.get();
        if (!verifyGrantSignature(km, grant)) {
            return ContinuationValidation.fail(Constants.FAILURE_GRANT_NOT_FOUND);
        }
        if (grant.getExpiresAt() != null && grant.getExpiresAt().compareTo(nowIso) <= 0) {
            return ContinuationValidation.fail(Constants.FAILURE_GRANT_EXPIRED);
        }
        if (!capability.equals(grant.getCapability())) {
            return ContinuationValidation.fail(Constants.FAILURE_GRANT_CAPABILITY_MISMATCH);
        }
        if (!grantScopeSubsetOfToken(
                grant.getScope() != null ? grant.getScope() : List.of(),
                tokenScope != null ? tokenScope : List.of())) {
            return ContinuationValidation.fail(Constants.FAILURE_GRANT_SCOPE_MISMATCH);
        }
        String submittedDigest = sha256Digest(parameters != null ? parameters : Map.of());
        if (!submittedDigest.equals(grant.getApprovedParametersDigest())) {
            return ContinuationValidation.fail(Constants.FAILURE_GRANT_PARAM_DRIFT);
        }
        if (ApprovalGrant.TYPE_SESSION_BOUND.equals(grant.getGrantType())) {
            if (tokenSessionId == null || tokenSessionId.isEmpty()
                    || !tokenSessionId.equals(grant.getSessionId())) {
                return ContinuationValidation.fail(Constants.FAILURE_GRANT_SESSION_INVALID);
            }
        }
        return ContinuationValidation.ok(grant);
    }
}
