package dev.anip.rest;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.service.ANIPService;
import dev.anip.service.JsonRequestBody;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * Shared route generation and parameter conversion for REST interface.
 * Framework-agnostic — used by both Spring and Quarkus adapters.
 *
 * Note: RouteOverride paths and methods affect OpenAPI metadata only.
 * HTTP routing always uses /api/{capability} dispatched by capability name.
 */
public final class RestRouter {

    private RestRouter() {}

    @SuppressWarnings("unchecked")
    public static List<RestRoute> generateRoutes(ANIPService service,
                                                  Map<String, RouteOverride> overrides) {
        List<RestRoute> routes = new ArrayList<>();
        Map<String, Object> manifest = (Map<String, Object>) service.getManifest();
        Map<String, Object> capabilities = (Map<String, Object>) manifest.get("capabilities");

        for (String name : capabilities.keySet()) {
            CapabilityDeclaration decl = service.getCapabilityDeclaration(name);
            if (decl == null) continue;

            String path = "/api/" + name;
            String method = "POST";
            if (decl.getSideEffect() != null && "read".equals(decl.getSideEffect().getType())) {
                method = "GET";
            }

            if (overrides != null && overrides.containsKey(name)) {
                RouteOverride override = overrides.get(name);
                if (override.getPath() != null && !override.getPath().isEmpty()) {
                    path = override.getPath();
                }
                if (override.getMethod() != null && !override.getMethod().isEmpty()) {
                    method = override.getMethod();
                }
            }

            routes.add(new RestRoute(name, path, method, decl));
        }
        return routes;
    }

    public static Map<String, Object> convertQueryParams(Map<String, String[]> rawParams,
                                                          CapabilityDeclaration decl) {
        Map<String, String> typeMap = new LinkedHashMap<>();
        if (decl.getInputs() != null) {
            for (CapabilityInput inp : decl.getInputs()) {
                typeMap.put(inp.getName(), inp.getType());
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        for (Map.Entry<String, String[]> entry : rawParams.entrySet()) {
            String key = entry.getKey();
            String[] values = entry.getValue();
            if (values == null || values.length == 0) continue;
            String value = values[0];

            result.put(key, convertQueryValue(value, typeMap.getOrDefault(key, "string")));
        }

        return result;
    }

    /** The JSON number grammar (RFC 8259 §6). */
    private static final Pattern JSON_NUMBER =
            Pattern.compile("-?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][+-]?[0-9]+)?");

    /**
     * Reads a query string value as the JSON value its declared type calls
     * for: a JSON number for integer and number, true or false for boolean,
     * JSON text for array and object (the only way a query string can carry
     * one). A value that cannot be read that way stays a string, and the
     * service's parameter validation (SPEC.md §6.3) refuses it by name.
     */
    static Object convertQueryValue(String value, String declaredType) {
        switch (declaredType) {
            case "integer", "number" -> {
                if (JSON_NUMBER.matcher(value).matches() && parseJson(value) instanceof Number number) {
                    return number;
                }
            }
            case "boolean" -> {
                if ("true".equals(value)) return true;
                if ("false".equals(value)) return false;
            }
            case "array" -> {
                if (parseJson(value) instanceof List<?> items) return items;
            }
            case "object" -> {
                if (parseJson(value) instanceof Map<?, ?> object) return object;
            }
            default -> { }
        }
        return value;
    }

    /** The value of a JSON text, as a request body would carry it; null when it is not JSON. */
    private static Object parseJson(String text) {
        try {
            return JsonRequestBody.parseValue(text.getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            return null;
        }
    }

    public static RestRoute findRoute(List<RestRoute> routes, String capabilityName) {
        for (RestRoute r : routes) {
            if (r.getCapabilityName().equals(capabilityName)) {
                return r;
            }
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> extractBodyParams(Map<String, Object> body) {
        if (body == null) return new LinkedHashMap<>();
        Map<String, Object> p = (Map<String, Object>) body.get("parameters");
        if (p != null) return p;
        Map<String, Object> result = new LinkedHashMap<>(body);
        result.remove("parameters");
        return result;
    }
}
