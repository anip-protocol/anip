package dev.anip.rest;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.SerializationFeature;

import dev.anip.core.ANIPError;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.Constants;
import dev.anip.core.DelegationToken;
import dev.anip.service.ANIPService;
import dev.anip.service.InvokeOpts;

import jakarta.servlet.http.HttpServletRequest;

import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * REST controller that dispatches to ANIP capabilities via /api/{capability}.
 * GET for read capabilities, POST for write/irreversible.
 * Also serves OpenAPI spec at /rest/openapi.json and Swagger UI at /rest/docs.
 */
@RestController
public class AnipRestController {

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
            .setSerializationInclusion(JsonInclude.Include.NON_NULL)
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
            .configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);

    private final ANIPService service;
    private final List<RestRoute> routes;
    private final Map<String, Object> openApiSpec;

    /**
     * Creates the REST controller from the service and optional route overrides.
     */
    public AnipRestController(ANIPService service, Map<String, RouteOverride> overrides) {
        this.service = service;
        this.routes = generateRoutes(service, overrides);
        this.openApiSpec = OpenApiGenerator.generateSpec(service.getServiceId(), routes);
    }

    public AnipRestController(ANIPService service) {
        this(service, null);
    }

    // --- OpenAPI ---

    @GetMapping(value = "/rest/openapi.json", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> openApi() {
        return ResponseEntity.ok(openApiSpec);
    }

    // --- Swagger UI ---

    @GetMapping(value = "/rest/docs", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> docs() {
        String html = """
                <!DOCTYPE html>
                <html><head><title>ANIP REST API</title>
                <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
                </head><body>
                <div id="swagger-ui"></div>
                <script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
                <script>SwaggerUIBundle({ url: "/rest/openapi.json", dom_id: "#swagger-ui" });</script>
                </body></html>""";
        return ResponseEntity.ok(html);
    }

    // --- Capability dispatchers ---

    @GetMapping(value = "/api/{capability}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> handleGet(@PathVariable String capability,
                                             HttpServletRequest request) {
        return handleRoute(capability, "GET", null, request);
    }

    @PostMapping(value = "/api/{capability}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> handlePost(@PathVariable String capability,
                                              @RequestBody(required = false) Map<String, Object> body,
                                              HttpServletRequest request) {
        return handleRoute(capability, "POST", body, request);
    }

    // --- Internal ---

    private ResponseEntity<Object> handleRoute(String capability, String method,
                                                Map<String, Object> body,
                                                HttpServletRequest request) {
        // Find route.
        RestRoute route = null;
        for (RestRoute r : routes) {
            if (r.getCapabilityName().equals(capability)) {
                route = r;
                break;
            }
        }
        if (route == null) {
            return failureResponse(404, Constants.FAILURE_UNKNOWN_CAPABILITY,
                    "Capability '" + capability + "' not found", false);
        }

        // Extract auth.
        String authHeader = request.getHeader("Authorization");
        String bearer = extractBearer(authHeader);
        if (bearer == null || bearer.isEmpty()) {
            Map<String, Object> failure = new LinkedHashMap<>();
            failure.put("type", Constants.FAILURE_AUTH_REQUIRED);
            failure.put("detail", "Authorization header with Bearer token or API key required");
            failure.put("resolution", Map.of(
                    "action", "provide_credentials",
                    "requires", "Bearer token or API key"
            ));
            failure.put("retry", true);

            Map<String, Object> resp = new LinkedHashMap<>();
            resp.put("success", false);
            resp.put("failure", failure);
            return ResponseEntity.status(401).body(resp);
        }

        DelegationToken token;
        try {
            token = RestAuthBridge.resolveAuth(bearer, service, capability);
        } catch (ANIPError e) {
            int status = Constants.failureStatusCode(e.getErrorType());
            return failureResponse(status, e.getErrorType(), e.getDetail(), e.isRetry());
        } catch (Exception e) {
            return failureResponse(500, Constants.FAILURE_INTERNAL_ERROR,
                    "Authentication failed", false);
        }

        // Extract parameters.
        Map<String, Object> params;
        if ("GET".equals(method)) {
            params = convertQueryParams(request, route.getDeclaration());
        } else {
            if (body == null) {
                body = new LinkedHashMap<>();
            }
            // Accept both {parameters: {...}} and flat body.
            @SuppressWarnings("unchecked")
            Map<String, Object> p = (Map<String, Object>) body.get("parameters");
            if (p != null) {
                params = p;
            } else {
                params = new LinkedHashMap<>(body);
                params.remove("parameters");
            }
        }

        String clientRefId = request.getHeader("X-Client-Reference-Id");
        InvokeOpts opts = new InvokeOpts(clientRefId, false);

        Map<String, Object> result = service.invoke(capability, token, params, opts);

        boolean success = Boolean.TRUE.equals(result.get("success"));
        if (!success) {
            @SuppressWarnings("unchecked")
            Map<String, Object> failure = (Map<String, Object>) result.get("failure");
            String failType = failure != null ? (String) failure.get("type") : null;
            int status = Constants.failureStatusCode(failType);
            return ResponseEntity.status(status).body(result);
        }

        return ResponseEntity.ok(result);
    }

    private String extractBearer(String authHeader) {
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            return authHeader.substring(7).trim();
        }
        return null;
    }

    private Map<String, Object> convertQueryParams(HttpServletRequest request,
                                                     CapabilityDeclaration decl) {
        Map<String, String> typeMap = new LinkedHashMap<>();
        if (decl.getInputs() != null) {
            for (CapabilityInput inp : decl.getInputs()) {
                typeMap.put(inp.getName(), inp.getType());
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        Map<String, String[]> paramMap = request.getParameterMap();
        for (Map.Entry<String, String[]> entry : paramMap.entrySet()) {
            String key = entry.getKey();
            String[] values = entry.getValue();
            if (values == null || values.length == 0) continue;
            String value = values[0];

            String inputType = typeMap.get(key);
            if (inputType == null) inputType = "string";

            switch (inputType) {
                case "integer" -> {
                    try {
                        result.put(key, Integer.parseInt(value));
                    } catch (NumberFormatException e) {
                        result.put(key, value);
                    }
                }
                case "number" -> {
                    try {
                        result.put(key, Double.parseDouble(value));
                    } catch (NumberFormatException e) {
                        result.put(key, value);
                    }
                }
                case "boolean" -> result.put(key, "true".equals(value));
                default -> result.put(key, value);
            }
        }

        return result;
    }

    private ResponseEntity<Object> failureResponse(int status, String type,
                                                     String detail, boolean retry) {
        Map<String, Object> failure = new LinkedHashMap<>();
        failure.put("type", type);
        failure.put("detail", detail);
        failure.put("retry", retry);

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("success", false);
        resp.put("failure", failure);
        return ResponseEntity.status(status).body(resp);
    }

    // --- Route generation ---

    private static List<RestRoute> generateRoutes(ANIPService service,
                                                    Map<String, RouteOverride> overrides) {
        List<RestRoute> routes = new ArrayList<>();
        // Iterate through all capabilities.
        @SuppressWarnings("unchecked")
        Map<String, Object> manifest = (Map<String, Object>) service.getManifest();
        @SuppressWarnings("unchecked")
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

    /**
     * Returns generated routes (for testing).
     */
    public List<RestRoute> getRoutes() {
        return routes;
    }
}
