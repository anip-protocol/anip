package dev.anip.service;

import com.fasterxml.jackson.databind.JsonNode;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.Constants;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Checks an invocation's parameters against the capability's declared inputs
 * (SPEC.md §6.3, "Parameter Validation").
 *
 * <p>The check is applied to the parameters as the caller sent them: a
 * required input must be present and not JSON {@code null} (unless its
 * declaration sets {@code resolution.on_missing}, in which case the handler
 * answers through that path: {@link CapabilityInput#mustBeSupplied()}), and a supplied
 * value whose declared type is one of the six primitive type names must be of
 * the matching JSON type. A parameter that names no declared input is
 * undeclared and refused. Missing inputs are reported first, then undeclared
 * parameters, then wrong types. Any other declared type name is not checked,
 * and {@code default}, {@code allowed_values} and the {@code resolution}
 * block play no part.</p>
 */
public final class ParameterValidation {

    /** The declared type names the runtime checks; any other name is a domain type. */
    private static final Set<String> PRIMITIVES =
            Set.of("string", "integer", "number", "boolean", "array", "object");

    static final String REQUIRES = "parameters that match the capability's declared inputs";

    private ParameterValidation() {}

    /**
     * Returns the failure detail when {@code parameters} do not match the
     * declared inputs, or {@code null} when they do.
     *
     * @param capability  the capability name, used in the detail
     * @param declaration the capability declaration
     * @param parameters  the parameters as the caller sent them; {@code null} counts as empty
     */
    public static String check(String capability, CapabilityDeclaration declaration,
                               Map<String, ?> parameters) {
        List<CapabilityInput> inputs = declaration != null && declaration.getInputs() != null
                ? declaration.getInputs() : List.of();
        Map<String, ?> supplied = parameters != null ? parameters : Map.of();

        List<String> missing = new ArrayList<>();
        for (CapabilityInput input : inputs) {
            if (input.mustBeSupplied() && isAbsent(supplied, input.getName())) {
                missing.add(input.getName());
            }
        }
        if (!missing.isEmpty()) {
            return capability + " is missing required input(s): " + String.join(", ", missing);
        }

        // Every key must name a declared input, whatever its value. Listed as
        // RFC 8785 sorts member names (§4.7): String order is UTF-16 code units.
        Set<String> declaredNames = new HashSet<>();
        for (CapabilityInput input : inputs) {
            declaredNames.add(input.getName());
        }
        List<String> undeclared = new ArrayList<>();
        for (String key : supplied.keySet()) {
            if (!declaredNames.contains(key)) {
                undeclared.add(key);
            }
        }
        if (!undeclared.isEmpty()) {
            Collections.sort(undeclared);
            return capability + " has undeclared parameter(s): " + String.join(", ", undeclared);
        }

        List<String> wrong = new ArrayList<>();
        for (CapabilityInput input : inputs) {
            if (isAbsent(supplied, input.getName())) {
                continue;
            }
            String declared = input.getType();
            if (declared == null || !PRIMITIVES.contains(declared)) {
                continue;
            }
            Object value = supplied.get(input.getName());
            String received = jsonType(value);
            boolean ok = switch (declared) {
                case "integer" -> "number".equals(received) && isIntegral(value);
                default -> declared.equals(received);
            };
            if (!ok) {
                wrong.add("'" + input.getName() + "' must be " + declared + ", got " + received);
            }
        }
        if (!wrong.isEmpty()) {
            return capability + " has invalid input(s): " + String.join("; ", wrong);
        }
        return null;
    }

    /**
     * The {@code invalid_parameters} failure for a detail returned by
     * {@link #check}: the same request cannot succeed, and nothing outside the
     * request has to change.
     */
    public static Map<String, Object> failure(String detail) {
        Map<String, Object> resolution = new LinkedHashMap<>();
        resolution.put("action", "retry_now");
        resolution.put("recovery_class", Constants.recoveryClassForAction("retry_now"));
        resolution.put("requires", REQUIRES);
        Map<String, Object> failure = new LinkedHashMap<>();
        failure.put("type", Constants.FAILURE_INVALID_PARAMETERS);
        failure.put("detail", detail);
        failure.put("resolution", resolution);
        failure.put("retry", false);
        return failure;
    }

    private static boolean isAbsent(Map<String, ?> parameters, String name) {
        return isJsonNull(parameters.get(name));
    }

    private static boolean isJsonNull(Object value) {
        return value == null
                || (value instanceof JsonNode node && (node.isNull() || node.isMissingNode()));
    }

    /**
     * The JSON type of a value in any of the in-memory representations a
     * transport hands to the service: {@code string}, {@code number},
     * {@code boolean}, {@code array} or {@code object}.
     */
    static String jsonType(Object value) {
        if (value instanceof JsonNode node) {
            if (node.isTextual()) return "string";
            if (node.isBoolean()) return "boolean";
            if (node.isNumber()) return "number";
            if (node.isArray()) return "array";
            return "object";
        }
        // A boolean is never a number; it is checked before anything numeric.
        if (value instanceof Boolean) return "boolean";
        if (value instanceof Number) return "number";
        if (value instanceof CharSequence || value instanceof Character) return "string";
        if (value instanceof Map) return "object";
        if (value instanceof Collection || value instanceof Iterable || value.getClass().isArray()) {
            return "array";
        }
        return "object";
    }

    /** True when a JSON number is finite and has no fractional part. */
    static boolean isIntegral(Object value) {
        if (value instanceof JsonNode node) {
            if (node.isIntegralNumber()) return true;
            if (node.isBigDecimal()) return isIntegral(node.decimalValue());
            return isIntegral(node.doubleValue());
        }
        if (value instanceof Integer || value instanceof Long || value instanceof Short
                || value instanceof Byte || value instanceof BigInteger
                || value instanceof AtomicInteger || value instanceof AtomicLong) {
            return true;
        }
        if (value instanceof BigDecimal decimal) {
            return decimal.signum() == 0 || decimal.stripTrailingZeros().scale() <= 0;
        }
        if (value instanceof Number number) {
            double d = number.doubleValue();
            return !Double.isNaN(d) && !Double.isInfinite(d) && d == Math.rint(d);
        }
        return false;
    }
}
