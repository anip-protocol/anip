package dev.anip.rest.spring;

import dev.anip.core.ANIPError;
import dev.anip.core.Constants;
import dev.anip.core.DelegationToken;
import dev.anip.rest.OpenApiGenerator;
import dev.anip.rest.RestAuthBridge;
import dev.anip.rest.RestRoute;
import dev.anip.rest.RestRouter;
import dev.anip.rest.RouteOverride;
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

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Spring MVC REST controller that dispatches to ANIP capabilities via /api/{capability}.
 * GET for read capabilities, POST for write/irreversible.
 * Also serves OpenAPI spec at /rest/openapi.json and Swagger UI at /rest/docs.
 */
@RestController
public class AnipRestController {

    private final ANIPService service;
    private final List<RestRoute> routes;
    private final Map<String, Object> openApiSpec;

    /**
     * Creates the REST controller from the service and optional route overrides.
     */
    public AnipRestController(ANIPService service, Map<String, RouteOverride> overrides) {
        this.service = service;
        this.routes = RestRouter.generateRoutes(service, overrides);
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
        RestRoute route = RestRouter.findRoute(routes, capability);
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
            params = RestRouter.convertQueryParams(request.getParameterMap(), route.getDeclaration());
        } else {
            params = RestRouter.extractBodyParams(body);
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

    /**
     * Returns generated routes (for testing).
     */
    public List<RestRoute> getRoutes() {
        return routes;
    }
}
