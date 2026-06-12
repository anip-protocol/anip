package dev.anip.generated.gtm_pipeline_q2_review;

import dev.anip.core.ANIPError;
import dev.anip.core.AuditPolicy;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.Composition;
import dev.anip.core.CompositionStep;
import dev.anip.core.FailurePolicy;
import dev.anip.core.GrantPolicy;
import dev.anip.core.InputMeaning;
import dev.anip.core.InputResolution;
import dev.anip.core.Constants;
import dev.anip.core.Resolution;
import dev.anip.core.ResolutionBehavior;
import dev.anip.core.ResolutionMode;
import dev.anip.core.SideEffect;
import dev.anip.service.CapabilityDef;
import dev.anip.service.InvocationContext;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class GeneratedCapabilities {

    private GeneratedCapabilities() {}

    public static List<CapabilityDef> createAll(BackendAdapter backendAdapter) {
        return createAll(backendAdapter, "");
    }

    public static List<CapabilityDef> createAll(BackendAdapter backendAdapter, String serviceFilter) {
        String normalizedServiceFilter = serviceFilter == null ? "" : serviceFilter.trim();
        return GeneratedRuntimeTarget.capabilities().stream()
                .filter(capability -> normalizedServiceFilter.isBlank() || normalizedServiceFilter.equals(stringValue(capability, "service_id")))
                .map(capability -> createCapability(capability, backendAdapter))
                .toList();
    }

    private static CapabilityDef createCapability(Map<String, Object> capability, BackendAdapter backendAdapter) {
        CapabilityDeclaration declaration = new CapabilityDeclaration(
                stringValue(capability, "capability_id"),
                firstNonEmpty(stringValue(capability, "summary"), stringValue(capability, "title"), stringValue(capability, "capability_id")),
                GeneratedRuntimeTarget.contractVersion(),
                buildInputs(capability),
                new CapabilityOutput(firstNonEmpty(stringValue(capability, "output_shape"), "governed_result"), List.of("execution_status", "capability_id", "semantic_input", "backend_input_contract", "note")),
                new SideEffect(sideEffectType(stringValue(capability, "side_effect_level")), rollbackWindowFor(stringValue(capability, "side_effect_level"))),
                stringList(capability.get("minimum_scope")),
                null,
                null,
                List.of("unary"),
                null,
                null,
                List.of(),
                List.of()
        )
                .setKind(declarationKind(capability))
                .setComposition(declarationComposition(capability))
                .setGrantPolicy(readGrantPolicy(capability.get("grant_policy")));
        return new CapabilityDef(declaration, (ctx, params) -> handle(capability, ctx, params, backendAdapter));
    }

    private static String declarationKind(Map<String, Object> capability) {
        String kind = firstNonEmpty(stringValue(capability, "kind"), "atomic");
        return kind;
    }

    private static Composition declarationComposition(Map<String, Object> capability) {
        return readComposition(capability.get("composition"));
    }

    private static Composition readComposition(Object value) {
        Map<String, Object> map = objectMap(value);
        if (map == null || map.isEmpty()) return null;
        List<CompositionStep> steps = new ArrayList<>();
        for (Map<String, Object> step : mapList(map.get("steps"))) {
            steps.add(new CompositionStep(stringValue(step, "id"), stringValue(step, "capability"))
                    .setEmptyResultSource(booleanValue(step.get("empty_result_source")))
                    .setEmptyResultPath(stringValue(step, "empty_result_path")));
        }
        Map<String, Object> failure = objectMap(map.get("failure_policy"));
        Map<String, Object> audit = objectMap(map.get("audit_policy"));
        Composition composition = new Composition(
                firstNonEmpty(stringValue(map, "authority_boundary"), "same_service"),
                steps,
                nestedStringMap(map.get("input_mapping")),
                stringMap(map.get("output_mapping")),
                new FailurePolicy(
                        firstNonEmpty(stringValue(failure, "child_clarification"), "propagate"),
                        firstNonEmpty(stringValue(failure, "child_denial"), "propagate"),
                        firstNonEmpty(stringValue(failure, "child_approval_required"), "propagate"),
                        firstNonEmpty(stringValue(failure, "child_error"), "fail_parent")),
                new AuditPolicy(booleanValue(value(audit, "record_child_invocations")), booleanValue(value(audit, "parent_task_lineage"))));
        String emptyResultPolicy = stringValue(map, "empty_result_policy");
        if (!emptyResultPolicy.isBlank()) composition.setEmptyResultPolicy(emptyResultPolicy);
        Map<String, Object> emptyResultOutput = objectMap(map.get("empty_result_output"));
        if (emptyResultOutput != null) composition.setEmptyResultOutput(emptyResultOutput);
        return composition;
    }

    private static GrantPolicy readGrantPolicy(Object value) {
        Map<String, Object> map = objectMap(value);
        if (map == null || map.isEmpty()) return null;
        return new GrantPolicy(
                stringList(map.get("allowed_grant_types")),
                stringValue(map, "default_grant_type"),
                intValue(map.get("expires_in_seconds")),
                intValue(map.get("max_uses")));
    }

    private static Map<String, Object> handle(Map<String, Object> capability, InvocationContext ctx, Map<String, Object> params, BackendAdapter backendAdapter) {
        params = applyInputDefaults(capability, params);
        assertRequiredSemanticInputs(capability, params);
        validateInputBehavior(capability, params);
        Policy.PolicyDecision policy = Policy.evaluate(capability, params, ctx.getRootPrincipal());
        if ("deny".equals(policy.decision())) {
            throw new ANIPError("denied", firstNonEmpty(policy.detail(), "Request denied for " + stringValue(capability, "capability_id") + ".")).withResolution("contact_service_owner");
        }
        if ("clarify".equals(policy.decision())) {
            throw new ANIPError("clarification_required", firstNonEmpty(policy.detail(), "Clarification required for " + stringValue(capability, "capability_id") + ".")).withResolution("obtain_binding");
        }

        Map<String, Object> plan = buildBackendInvocationPlan(capability, params);
        if ("approval_required".equals(policy.decision()) && (ctx.getApprovalGrant() == null || ctx.getApprovalGrant().isBlank())) {
            throw new ANIPError("approval_required", firstNonEmpty(policy.detail(), "Approval required for " + stringValue(capability, "capability_id") + ".")).withResolution("request_approval");
        }
        return backendAdapter.execute(capability, plan, objectMap(plan.get("adapter_input")), ctx);
    }

    private static List<CapabilityInput> buildInputs(Map<String, Object> capability) {
        List<CapabilityInput> inputs = new ArrayList<>();
        for (Map<String, Object> input : inputList(capability, "required_inputs")) {
            inputs.add(new CapabilityInput(
                    stringValue(input, "input_name"),
                    firstNonEmpty(stringValue(input, "input_type"), "string"),
                    true,
                    defaultValue(input),
                    firstNonEmpty(stringValue(input, "summary"), stringValue(input, "input_name")),
                    optionalString(input, "semantic_type"),
                    booleanValue(input.get("entity_reference")),
                    stringList(input.get("allowed_values")),
                    optionalString(input, "catalog_ref"),
                    inputMeanings(input.get("input_meanings")),
                    inputResolution(input.get("resolution"))
            ));
        }
        for (Map<String, Object> input : inputList(capability, "optional_inputs")) {
            inputs.add(new CapabilityInput(
                    stringValue(input, "input_name"),
                    firstNonEmpty(stringValue(input, "input_type"), "string"),
                    false,
                    defaultValue(input),
                    firstNonEmpty(stringValue(input, "summary"), stringValue(input, "input_name")),
                    optionalString(input, "semantic_type"),
                    booleanValue(input.get("entity_reference")),
                    stringList(input.get("allowed_values")),
                    optionalString(input, "catalog_ref"),
                    inputMeanings(input.get("input_meanings")),
                    inputResolution(input.get("resolution"))
            ));
        }
        return inputs;
    }

    private static InputResolution inputResolution(Object value) {
        Map<String, Object> map = objectMap(value);
        if (map == null || map.isEmpty()) return null;
        return new InputResolution(
                resolutionMode(stringValue(map, "mode")),
                optionalString(map, "resolver_ref"),
                resolutionBehavior(stringValue(map, "on_missing")),
                resolutionBehavior(stringValue(map, "on_ambiguous")),
                resolutionBehavior(stringValue(map, "on_unresolved")));
    }

    private static ResolutionMode resolutionMode(String value) {
        return value.isBlank() ? null : ResolutionMode.fromWire(value);
    }

    private static ResolutionBehavior resolutionBehavior(String value) {
        return value.isBlank() ? null : ResolutionBehavior.fromWire(value);
    }

    private static List<InputMeaning> inputMeanings(Object value) {
        List<InputMeaning> result = new ArrayList<>();
        for (Map<String, Object> item : mapList(value)) {
            result.add(new InputMeaning(
                    stringValue(item, "label"),
                    stringValue(item, "value"),
                    stringValue(item, "description")));
        }
        return result;
    }

    private static void assertRequiredSemanticInputs(Map<String, Object> capability, Map<String, Object> params) {
        List<String> missing = new ArrayList<>();
        for (Map<String, Object> input : inputList(capability, "required_inputs")) {
            if (!stringValue(input, "default_value").isBlank()) continue;
            String inputName = stringValue(input, "input_name");
            Object value = params.get(inputName);
            if (value == null) {
                missing.add(inputName);
                continue;
            }
            if (value instanceof String text && text.isBlank()) {
                missing.add(inputName);
            }
        }
        if (!missing.isEmpty()) {
            throw new ANIPError("clarification_required", "Required semantic inputs are missing for " + stringValue(capability, "capability_id") + ".")
                    .withResolution(new Resolution("obtain_binding", Constants.recoveryClassForAction("obtain_binding"), String.join(",", missing), null, null));
        }
    }

    private static void validateInputBehavior(Map<String, Object> capability, Map<String, Object> params) {
        List<Map<String, Object>> inputs = new ArrayList<>();
        inputs.addAll(inputList(capability, "required_inputs"));
        inputs.addAll(inputList(capability, "optional_inputs"));
        for (Map<String, Object> input : inputs) {
            String inputName = stringValue(input, "input_name");
            Object value = params.get(inputName);
            if (inputName.isBlank() || value == null || String.valueOf(value).isBlank()) continue;
            List<String> allowedValues = stringList(input.get("allowed_values"));
            if (allowedValues.isEmpty() || allowedValues.contains(String.valueOf(value))) continue;
            Map<String, Object> resolution = objectMap(input.get("resolution"));
            boolean shouldDeny = "closed_values".equals(stringValue(resolution, "mode")) && "deny".equals(stringValue(resolution, "on_unresolved"));
            String action = shouldDeny ? "contact_service_owner" : "obtain_binding";
            throw new ANIPError(shouldDeny ? "denied" : "clarification_required", "Input " + inputName + " must use one of the declared allowed values.")
                    .withResolution(new Resolution(action, Constants.recoveryClassForAction(action), inputName, null, null));
        }
    }

    private static Object defaultValue(Map<String, Object> input) {
        String value = stringValue(input, "default_value");
        return value.isBlank() ? null : value;
    }

    private static Map<String, Object> applyInputDefaults(Map<String, Object> capability, Map<String, Object> params) {
        Map<String, Object> normalized = new LinkedHashMap<>(params);
        List<Map<String, Object>> inputs = new ArrayList<>();
        inputs.addAll(inputList(capability, "required_inputs"));
        inputs.addAll(inputList(capability, "optional_inputs"));
        for (Map<String, Object> input : inputs) {
            String inputName = stringValue(input, "input_name");
            String defaultValue = stringValue(input, "default_value");
            Map<String, Object> resolution = objectMap(input.get("resolution"));
            if ("omit".equals(stringValue(resolution, "on_missing"))) continue;
            Object value = normalized.get(inputName);
            if (!inputName.isBlank() && !defaultValue.isBlank() && (value == null || value instanceof String text && text.isBlank())) {
                normalized.put(inputName, defaultValue);
            }
        }
        return normalized;
    }

    private static Map<String, Object> buildBackendInvocationPlan(Map<String, Object> capability, Map<String, Object> params) {
        Map<String, Object> selectedBinding = selectBackendBinding(capability);
        Map<String, Object> contract = effectiveBackendInputContract(capability, selectedBinding);
        Set<String> semanticKeys = new LinkedHashSet<>();
        for (Map<String, Object> input : inputList(capability, "required_inputs")) {
            semanticKeys.add(stringValue(input, "input_name"));
        }
        for (Map<String, Object> input : inputList(capability, "optional_inputs")) {
            semanticKeys.add(stringValue(input, "input_name"));
        }
        Map<String, Object> semanticInput = new LinkedHashMap<>();
        for (Map.Entry<String, Object> entry : params.entrySet()) {
            if (semanticKeys.contains(entry.getKey())) {
                semanticInput.put(entry.getKey(), entry.getValue());
            }
        }
        Set<String> adapterKeys = new LinkedHashSet<>(semanticKeys);
        adapterKeys.addAll(stringList(contract.get("required")));
        adapterKeys.addAll(stringList(contract.get("optional")));
        Map<String, Object> adapterInput = new LinkedHashMap<>();
        for (Map.Entry<String, Object> entry : params.entrySet()) {
            if (adapterKeys.contains(entry.getKey())) {
                adapterInput.put(entry.getKey(), entry.getValue());
            }
        }
        List<String> unresolved = new ArrayList<>();
        for (String key : stringList(contract.get("required"))) {
            if (!params.containsKey(key) || params.get(key) == null) {
                unresolved.add(key);
            }
        }
        Map<String, Object> plan = new LinkedHashMap<>();
        plan.put("selected_binding", selectedBinding);
        plan.put("semantic_input", semanticInput);
        plan.put("adapter_input", adapterInput);
        plan.put("backend_input_contract", contract);
        plan.put("unresolved_required_backend_inputs", unresolved);
        return plan;
    }

    private static Map<String, Object> selectBackendBinding(Map<String, Object> capability) {
        List<Map<String, Object>> bindings = mapList(capability.get("backend_bindings"));
        if (bindings.isEmpty()) {
            return null;
        }
        return bindings.get(0);
    }

    private static Map<String, Object> effectiveBackendInputContract(Map<String, Object> capability, Map<String, Object> selectedBinding) {
        String mode = firstNonEmpty(stringValue(selectedBinding, "backend_input_mode"), stringValue(capability, "backend_input_mode"), "implicit");
        List<String> derivedRequired = firstNonEmptyList(stringList(value(selectedBinding, "derived_required_backend_inputs")), stringList(capability.get("derived_required_backend_inputs")));
        List<String> derivedOptional = firstNonEmptyList(stringList(value(selectedBinding, "derived_optional_backend_inputs")), stringList(capability.get("derived_optional_backend_inputs")));
        List<String> explicitRequired = firstNonEmptyList(stringList(value(selectedBinding, "explicit_required_backend_inputs")), stringList(capability.get("explicit_required_backend_inputs")));
        List<String> explicitOptional = firstNonEmptyList(stringList(value(selectedBinding, "explicit_optional_backend_inputs")), stringList(capability.get("explicit_optional_backend_inputs")));

        Map<String, Object> result = new LinkedHashMap<>();
        if ("explicit".equals(mode)) {
            List<String> required = uniqueStrings(explicitRequired);
            result.put("mode", "explicit");
            result.put("required", required);
            result.put("optional", exclude(uniqueStrings(explicitOptional), required));
            return result;
        }
        if ("hybrid".equals(mode)) {
            List<String> required = uniqueStrings(concat(derivedRequired, explicitRequired));
            result.put("mode", "hybrid");
            result.put("required", required);
            result.put("optional", exclude(uniqueStrings(concat(derivedOptional, explicitOptional)), required));
            return result;
        }
        List<String> required = uniqueStrings(derivedRequired);
        result.put("mode", "implicit");
        result.put("required", required);
        result.put("optional", exclude(uniqueStrings(derivedOptional), required));
        return result;
    }

    private static List<String> governanceList(Map<String, Object> capability, String key) {
        Object governance = capability.get("governance");
        if (governance instanceof Map<?, ?> map) {
            return stringList(map.get(key));
        }
        return List.of();
    }

    private static Object value(Map<String, Object> object, String key) {
        if (object == null) {
            return null;
        }
        return object.get(key);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> objectMap(Object value) {
        if (value instanceof Map<?, ?> map) {
            return (Map<String, Object>) map;
        }
        return null;
    }

    private static Map<String, String> stringMap(Object value) {
        Map<String, Object> map = objectMap(value);
        if (map == null) {
            return Map.of();
        }
        Map<String, String> result = new LinkedHashMap<>();
        for (Map.Entry<String, Object> entry : map.entrySet()) {
            if (entry.getValue() != null) result.put(entry.getKey(), String.valueOf(entry.getValue()));
        }
        return result;
    }

    private static Map<String, Map<String, String>> nestedStringMap(Object value) {
        Map<String, Object> map = objectMap(value);
        if (map == null) {
            return Map.of();
        }
        Map<String, Map<String, String>> result = new LinkedHashMap<>();
        for (Map.Entry<String, Object> entry : map.entrySet()) {
            result.put(entry.getKey(), stringMap(entry.getValue()));
        }
        return result;
    }

    private static boolean booleanValue(Object value) {
        return value instanceof Boolean bool && bool;
    }

    private static int intValue(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        if (value instanceof String text && !text.isBlank()) {
            return Integer.parseInt(text);
        }
        return 0;
    }

    private static String stringValue(Map<String, Object> object, String key) {
        Object value = value(object, key);
        if (value == null) {
            return "";
        }
        return String.valueOf(value);
    }

    private static String optionalString(Map<String, Object> object, String key) {
        String value = stringValue(object, key);
        return value.isBlank() ? null : value;
    }

    private static String firstNonEmpty(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return "";
    }

    private static List<String> firstNonEmptyList(List<String> primary, List<String> fallback) {
        if (!primary.isEmpty()) {
            return primary;
        }
        return fallback;
    }

    private static List<String> uniqueStrings(List<String> values) {
        List<String> result = new ArrayList<>();
        for (String value : values) {
            if (value == null || value.isBlank() || result.contains(value)) {
                continue;
            }
            result.add(value);
        }
        return result;
    }

    private static List<String> concat(List<String> left, List<String> right) {
        List<String> result = new ArrayList<>(left);
        result.addAll(right);
        return result;
    }

    private static List<String> exclude(List<String> values, List<String> excluded) {
        List<String> result = new ArrayList<>();
        for (String value : values) {
            if (!excluded.contains(value)) {
                result.add(value);
            }
        }
        return result;
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> inputList(Map<String, Object> capability, String key) {
        return mapList(capability.get(key));
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> mapList(Object value) {
        if (value instanceof List<?> list) {
            return (List<Map<String, Object>>) (List<?>) list;
        }
        return List.of();
    }

    @SuppressWarnings("unchecked")
    private static List<String> stringList(Object value) {
        if (value instanceof List<?> list) {
            return (List<String>) (List<?>) list;
        }
        return List.of();
    }

    private static String sideEffectType(String sideEffectLevel) {
        String value = sideEffectLevel == null ? "" : sideEffectLevel.toLowerCase();
        if (value.contains("irreversible")) {
            return "irreversible";
        }
        if (value.contains("transaction")) {
            return "transactional";
        }
        if (value.contains("write")) {
            return "write";
        }
        return "read";
    }

    private static String rollbackWindowFor(String sideEffectLevel) {
        return switch (sideEffectType(sideEffectLevel)) {
            case "read" -> "not_applicable";
            case "irreversible" -> "none";
            default -> "PT15M";
        };
    }
}
