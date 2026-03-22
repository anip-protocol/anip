package dev.anip.graphql;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Maps ANIP snake_case invoke results to GraphQL camelCase response shape.
 */
public class GraphQLResponseMapper {

    private GraphQLResponseMapper() {}

    /**
     * Converts snake_case to camelCase.
     * e.g. "cost_actual" -> "costActual"
     */
    public static String toCamelCase(String snake) {
        if (snake == null || snake.isEmpty()) return snake;
        String[] parts = snake.split("_");
        StringBuilder sb = new StringBuilder(parts[0]);
        for (int i = 1; i < parts.length; i++) {
            if (!parts[i].isEmpty()) {
                sb.append(Character.toUpperCase(parts[i].charAt(0)));
                sb.append(parts[i].substring(1));
            }
        }
        return sb.toString();
    }

    /**
     * Converts camelCase to snake_case.
     * e.g. "searchFlights" -> "search_flights"
     */
    public static String toSnakeCase(String camel) {
        if (camel == null || camel.isEmpty()) return camel;
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < camel.length(); i++) {
            char c = camel.charAt(i);
            if (Character.isUpperCase(c)) {
                if (i > 0) sb.append('_');
                sb.append(Character.toLowerCase(c));
            } else {
                sb.append(c);
            }
        }
        return sb.toString();
    }

    /**
     * Converts snake_case to PascalCase.
     */
    public static String toPascalCase(String snake) {
        if (snake == null || snake.isEmpty()) return snake;
        String[] parts = snake.split("_");
        StringBuilder sb = new StringBuilder();
        for (String part : parts) {
            if (!part.isEmpty()) {
                sb.append(Character.toUpperCase(part.charAt(0)));
                sb.append(part.substring(1));
            }
        }
        return sb.toString();
    }

    /**
     * Maps an ANIP invoke result (snake_case) to GraphQL result shape (camelCase).
     */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> buildGraphQLResponse(Map<String, Object> result) {
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("success", result.getOrDefault("success", false));
        response.put("result", result.get("result"));
        response.put("costActual", null);
        response.put("failure", null);

        Object costActualRaw = result.get("cost_actual");
        if (costActualRaw instanceof Map) {
            Map<String, Object> costMap = (Map<String, Object>) costActualRaw;
            Map<String, Object> mapped = new LinkedHashMap<>();
            mapped.put("financial", costMap.get("financial"));
            mapped.put("varianceFromEstimate", costMap.get("variance_from_estimate"));
            response.put("costActual", mapped);
        }

        Object failureRaw = result.get("failure");
        if (failureRaw instanceof Map) {
            Map<String, Object> failure = (Map<String, Object>) failureRaw;
            Map<String, Object> f = new LinkedHashMap<>();
            f.put("type", failure.getOrDefault("type", "unknown"));
            f.put("detail", failure.getOrDefault("detail", ""));
            f.put("resolution", null);
            f.put("retry", failure.getOrDefault("retry", false));

            Object resolutionRaw = failure.get("resolution");
            if (resolutionRaw instanceof Map) {
                Map<String, Object> res = (Map<String, Object>) resolutionRaw;
                Map<String, Object> mappedRes = new LinkedHashMap<>();
                mappedRes.put("action", res.get("action"));
                mappedRes.put("requires", res.get("requires"));
                mappedRes.put("grantableBy", res.get("grantable_by"));
                f.put("resolution", mappedRes);
            }

            response.put("failure", f);
        }

        return response;
    }
}
