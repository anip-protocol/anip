package dev.anip.rest.quarkus;

import dev.anip.core.ANIPError;
import dev.anip.core.Budget;
import dev.anip.core.Constants;
import dev.anip.core.DelegationToken;
import dev.anip.rest.OpenApiGenerator;
import dev.anip.rest.RestAuthBridge;
import dev.anip.rest.RestRoute;
import dev.anip.rest.RestRouter;
import dev.anip.rest.RouteOverride;
import dev.anip.service.ANIPService;
import dev.anip.service.InvokeOpts;

import jakarta.annotation.PostConstruct;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.HeaderParam;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.UriInfo;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Quarkus JAX-RS resource that dispatches to ANIP capabilities via /api/{capability}.
 * GET for read capabilities, POST for write/irreversible.
 * Also serves OpenAPI spec at /rest/openapi.json and Swagger UI at /rest/docs.
 */
@ApplicationScoped
@Path("/")
public class AnipRestResource {

    @Inject
    ANIPService service;

    @Inject
    Instance<Map<String, RouteOverride>> overridesInstance;

    private List<RestRoute> routes;
    private Map<String, Object> openApiSpec;

    @PostConstruct
    void init() {
        Map<String, RouteOverride> overrides = overridesInstance.isResolvable()
                ? overridesInstance.get() : null;
        this.routes = RestRouter.generateRoutes(service, overrides);
        this.openApiSpec = OpenApiGenerator.generateSpec(service.getServiceId(), routes);
    }

    // --- OpenAPI ---

    @GET
    @Path("/rest/openapi.json")
    @Produces(MediaType.APPLICATION_JSON)
    public Response openApi() {
        return Response.ok(openApiSpec).build();
    }

    // --- Swagger UI ---

    @GET
    @Path("/rest/docs")
    @Produces(MediaType.TEXT_HTML)
    public Response docs() {
        String html = """
                <!DOCTYPE html>
                <html><head><title>ANIP REST API</title>
                <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
                </head><body>
                <div id="swagger-ui"></div>
                <script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
                <script>SwaggerUIBundle({ url: "/rest/openapi.json", dom_id: "#swagger-ui" });</script>
                </body></html>""";
        return Response.ok(html).build();
    }

    // --- Capability dispatchers ---

    @GET
    @Path("/api/{capability}")
    @Produces(MediaType.APPLICATION_JSON)
    public Response handleGet(@PathParam("capability") String capability,
                               @HeaderParam("Authorization") String authHeader,
                               @HeaderParam("X-Client-Reference-Id") String clientRefId,
                               @HeaderParam("X-Anip-Approval-Grant") String approvalGrant,
                               @Context UriInfo uriInfo) {
        // Extract query params.
        Map<String, String[]> rawParams = new LinkedHashMap<>();
        uriInfo.getQueryParameters().forEach((k, v) -> rawParams.put(k, v.toArray(new String[0])));

        return handleRoute(capability, "GET", null, rawParams, authHeader, clientRefId, approvalGrant);
    }

    @POST
    @Path("/api/{capability}")
    @Consumes(MediaType.APPLICATION_JSON)
    @Produces(MediaType.APPLICATION_JSON)
    public Response handlePost(@PathParam("capability") String capability,
                                @HeaderParam("Authorization") String authHeader,
                                @HeaderParam("X-Client-Reference-Id") String clientRefId,
                                @HeaderParam("X-Anip-Approval-Grant") String approvalGrant,
                                Map<String, Object> body) {
        return handleRoute(capability, "POST", body, null, authHeader, clientRefId, approvalGrant);
    }

    // --- Internal ---

    private Response handleRoute(String capability, String method,
                                  Map<String, Object> body,
                                  Map<String, String[]> queryParams,
                                  String authHeader, String clientRefId,
                                  String approvalGrant) {
        // Find route.
        RestRoute route = RestRouter.findRoute(routes, capability);
        if (route == null) {
            return failureResponse(404, Constants.FAILURE_UNKNOWN_CAPABILITY,
                    "Capability '" + capability + "' not found", false);
        }

        // Extract auth.
        String bearer = extractBearer(authHeader);
        if (bearer == null || bearer.isEmpty()) {
            Map<String, Object> failure = new LinkedHashMap<>();
            failure.put("type", Constants.FAILURE_AUTH_REQUIRED);
            failure.put("detail", "Authorization header with Bearer token or API key required");
            failure.put("resolution", Map.of(
                    "action", "provide_credentials",
                    "recovery_class", Constants.recoveryClassForAction("provide_credentials"),
                    "requires", "Bearer token or API key"
            ));
            failure.put("retry", true);

            Map<String, Object> resp = new LinkedHashMap<>();
            resp.put("success", false);
            resp.put("failure", failure);
            return Response.status(401).entity(resp).build();
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
            params = RestRouter.convertQueryParams(queryParams, route.getDeclaration());
        } else {
            params = RestRouter.extractBodyParams(body);
        }

        InvokeOpts opts = new InvokeOpts(clientRefId, false);

        // Extract budget from request body.
        Budget budget = extractBudget(body);
        if (budget != null) {
            opts.setBudget(budget);
        }

        // v0.23: REST adapter wraps the entire body as capability parameters,
        // so approval_grant rides on X-Anip-Approval-Grant. session_id for
        // session_bound grants is read from the signed token, never the header.
        if (approvalGrant != null && !approvalGrant.isEmpty()) {
            opts.setApprovalGrant(approvalGrant);
        }

        Map<String, Object> result = service.invoke(capability, token, params, opts);

        boolean success = Boolean.TRUE.equals(result.get("success"));
        if (!success) {
            @SuppressWarnings("unchecked")
            Map<String, Object> failure = (Map<String, Object>) result.get("failure");
            String failType = failure != null ? (String) failure.get("type") : null;
            int status = Constants.failureStatusCode(failType);
            return Response.status(status).entity(result).build();
        }

        return Response.ok(result).build();
    }

    @SuppressWarnings("unchecked")
    private Budget extractBudget(Map<String, Object> body) {
        if (body == null) return null;
        Object budgetRaw = body.get("budget");
        if (!(budgetRaw instanceof Map)) return null;
        Map<String, Object> budgetMap = (Map<String, Object>) budgetRaw;
        String currency = budgetMap.get("currency") instanceof String s ? s : null;
        double maxAmount = budgetMap.get("max_amount") instanceof Number n ? n.doubleValue() : 0;
        if (currency != null && !currency.isEmpty() && maxAmount > 0) {
            return new Budget(currency, maxAmount);
        }
        return null;
    }

    private String extractBearer(String authHeader) {
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            return authHeader.substring(7).trim();
        }
        return null;
    }

    private Response failureResponse(int status, String type,
                                      String detail, boolean retry) {
        Map<String, Object> failure = new LinkedHashMap<>();
        failure.put("type", type);
        failure.put("detail", detail);
        failure.put("retry", retry);

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("success", false);
        resp.put("failure", failure);
        return Response.status(status).entity(resp).build();
    }

    /**
     * Returns generated routes (for testing).
     */
    public List<RestRoute> getRoutes() {
        return routes;
    }
}
