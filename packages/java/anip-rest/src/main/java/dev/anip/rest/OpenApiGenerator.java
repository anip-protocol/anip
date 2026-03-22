package dev.anip.rest;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Generates an OpenAPI 3.1 specification from ANIP capabilities.
 */
public class OpenApiGenerator {

    private static final Map<String, String> TYPE_MAP = Map.of(
            "string", "string",
            "integer", "integer",
            "number", "number",
            "boolean", "boolean",
            "date", "string",
            "airport_code", "string"
    );

    private OpenApiGenerator() {}

    /**
     * Maps an ANIP input type to an OpenAPI type.
     */
    public static String mapType(String anipType) {
        return TYPE_MAP.getOrDefault(anipType, "string");
    }

    /**
     * Generates a full OpenAPI 3.1 spec from the given routes.
     */
    public static Map<String, Object> generateSpec(String serviceId, List<RestRoute> routes) {
        Map<String, Object> paths = new LinkedHashMap<>();

        for (RestRoute route : routes) {
            String method = route.getMethod().toLowerCase();
            CapabilityDeclaration decl = route.getDeclaration();

            String seType = "";
            if (decl.getSideEffect() != null && decl.getSideEffect().getType() != null) {
                seType = decl.getSideEffect().getType();
            }
            if (seType.isEmpty()) {
                seType = "read";
            }

            List<String> minScope = decl.getMinimumScope();
            if (minScope == null) {
                minScope = List.of();
            }

            boolean financial = decl.getCost() != null && decl.getCost().getFinancial() != null;

            Map<String, Object> operation = new LinkedHashMap<>();
            operation.put("summary", decl.getDescription());
            operation.put("operationId", route.getCapabilityName());

            Map<String, Object> responses = new LinkedHashMap<>();
            responses.put("200", Map.of("description", "Success",
                    "content", Map.of("application/json", Map.of(
                            "schema", Map.of("$ref", "#/components/schemas/ANIPResponse")
                    ))));
            responses.put("401", Map.of("description", "Authentication required"));
            responses.put("403", Map.of("description", "Authorization failed"));
            responses.put("404", Map.of("description", "Unknown capability"));
            operation.put("responses", responses);

            operation.put("x-anip-side-effect", seType);
            operation.put("x-anip-minimum-scope", minScope);
            operation.put("x-anip-financial", financial);

            if ("get".equals(method)) {
                operation.put("parameters", buildQueryParameters(decl));
            } else {
                operation.put("requestBody", buildRequestBody(decl));
            }

            paths.put(route.getPath(), Map.of(method, operation));
        }

        Map<String, Object> spec = new LinkedHashMap<>();
        spec.put("openapi", "3.1.0");
        spec.put("info", Map.of("title", "ANIP REST — " + serviceId, "version", "1.0"));
        spec.put("paths", paths);

        Map<String, Object> components = new LinkedHashMap<>();
        Map<String, Object> schemas = new LinkedHashMap<>();
        schemas.put("ANIPResponse", Map.of(
                "type", "object",
                "properties", Map.of(
                        "success", Map.of("type", "boolean"),
                        "result", Map.of("type", "object"),
                        "invocation_id", Map.of("type", "string"),
                        "failure", Map.of("$ref", "#/components/schemas/ANIPFailure")
                )
        ));
        schemas.put("ANIPFailure", Map.of(
                "type", "object",
                "properties", Map.of(
                        "type", Map.of("type", "string"),
                        "detail", Map.of("type", "string"),
                        "resolution", Map.of("type", "object"),
                        "retry", Map.of("type", "boolean")
                )
        ));
        components.put("schemas", schemas);
        components.put("securitySchemes", Map.of(
                "bearer", Map.of("type", "http", "scheme", "bearer", "bearerFormat", "JWT")
        ));
        spec.put("components", components);
        spec.put("security", List.of(Map.of("bearer", List.of())));

        return spec;
    }

    private static List<Map<String, Object>> buildQueryParameters(CapabilityDeclaration decl) {
        List<Map<String, Object>> params = new ArrayList<>();
        if (decl.getInputs() == null) return params;

        for (CapabilityInput inp : decl.getInputs()) {
            Map<String, Object> schema = new LinkedHashMap<>();
            schema.put("type", mapType(inp.getType()));
            if ("date".equals(inp.getType())) {
                schema.put("format", "date");
            }
            if (inp.getDefaultValue() != null) {
                schema.put("default", inp.getDefaultValue());
            }

            Map<String, Object> param = new LinkedHashMap<>();
            param.put("name", inp.getName());
            param.put("in", "query");
            param.put("required", inp.isRequired());
            param.put("schema", schema);
            param.put("description", inp.getDescription());
            params.add(param);
        }
        return params;
    }

    private static Map<String, Object> buildRequestBody(CapabilityDeclaration decl) {
        Map<String, Object> properties = new LinkedHashMap<>();
        List<String> required = new ArrayList<>();

        if (decl.getInputs() != null) {
            for (CapabilityInput inp : decl.getInputs()) {
                Map<String, Object> prop = new LinkedHashMap<>();
                prop.put("type", mapType(inp.getType()));
                prop.put("description", inp.getDescription());
                if ("date".equals(inp.getType())) {
                    prop.put("format", "date");
                }
                properties.put(inp.getName(), prop);
                if (inp.isRequired()) {
                    required.add(inp.getName());
                }
            }
        }

        Map<String, Object> schema = new LinkedHashMap<>();
        schema.put("type", "object");
        schema.put("properties", properties);
        if (!required.isEmpty()) {
            schema.put("required", required);
        }

        return Map.of(
                "required", true,
                "content", Map.of(
                        "application/json", Map.of("schema", schema)
                )
        );
    }
}
