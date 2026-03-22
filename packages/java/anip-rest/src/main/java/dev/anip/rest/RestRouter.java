package dev.anip.rest;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.service.ANIPService;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

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

            String inputType = typeMap.getOrDefault(key, "string");

            switch (inputType) {
                case "integer" -> {
                    try { result.put(key, Integer.parseInt(value)); }
                    catch (NumberFormatException e) { result.put(key, value); }
                }
                case "number" -> {
                    try { result.put(key, Double.parseDouble(value)); }
                    catch (NumberFormatException e) { result.put(key, value); }
                }
                case "boolean" -> result.put(key, "true".equals(value));
                default -> result.put(key, value);
            }
        }

        return result;
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
