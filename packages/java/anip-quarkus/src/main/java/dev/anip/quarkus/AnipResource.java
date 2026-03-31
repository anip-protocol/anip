package dev.anip.quarkus;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.SerializationFeature;

import dev.anip.core.ANIPError;
import dev.anip.core.AuditFilters;
import dev.anip.core.AuditResponse;
import dev.anip.core.CheckpointDetailResponse;
import dev.anip.core.CheckpointListResponse;
import dev.anip.core.Constants;
import dev.anip.core.DelegationToken;
import dev.anip.core.HealthReport;
import dev.anip.core.PermissionResponse;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.service.ANIPService;
import dev.anip.service.InvokeOpts;
import dev.anip.service.SignedManifest;
import dev.anip.service.StreamEvent;
import dev.anip.service.StreamResult;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.HeaderParam;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.WebApplicationException;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.StreamingOutput;
import jakarta.ws.rs.core.UriInfo;

import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.io.IOException;
import java.io.OutputStream;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.TimeUnit;

/**
 * Quarkus JAX-RS resource implementing all 9 ANIP protocol routes plus health.
 */
@Path("/")
@ApplicationScoped
public class AnipResource {

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
            .setSerializationInclusion(JsonInclude.Include.NON_NULL)
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
            .configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);

    @Inject
    ANIPService service;

    @ConfigProperty(name = "anip.health.enabled", defaultValue = "true")
    boolean healthEnabled;

    // --- 1. Discovery ---

    @GET
    @Path(".well-known/anip")
    @Produces(MediaType.APPLICATION_JSON)
    public Response discovery(@Context UriInfo uriInfo) {
        String baseUrl = deriveBaseUrl(uriInfo);
        Map<String, Object> doc = service.getDiscovery(baseUrl);
        return Response.ok(doc).build();
    }

    // --- 2. JWKS ---

    @GET
    @Path(".well-known/jwks.json")
    @Produces(MediaType.APPLICATION_JSON)
    public Response jwks() {
        return Response.ok(service.getJwks()).build();
    }

    // --- 3. Manifest ---

    @GET
    @Path("anip/manifest")
    @Produces(MediaType.APPLICATION_JSON)
    public Response manifest() {
        SignedManifest sm = service.getSignedManifest();
        return Response.ok(sm.getManifestJson())
                .header("X-ANIP-Signature", sm.getSignature())
                .type(MediaType.APPLICATION_JSON_TYPE)
                .build();
    }

    // --- 4. Token issuance (bootstrap auth only) ---

    @POST
    @Path("anip/tokens")
    @Produces(MediaType.APPLICATION_JSON)
    public Response issueToken(Map<String, Object> body,
                               @HeaderParam("Authorization") String authHeader) {
        String bearer = extractBearer(authHeader);
        if (bearer == null || bearer.isEmpty()) {
            return authRequiredResponse();
        }

        // Bootstrap auth only.
        Optional<String> principal = service.authenticateBearer(bearer);
        if (principal.isEmpty()) {
            return failureResponse(401, Constants.FAILURE_INVALID_TOKEN,
                    "Invalid bootstrap credential", true);
        }

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> purposeParams = (Map<String, Object>) body.get("purpose_parameters");

            @SuppressWarnings("unchecked")
            List<String> scope = body.get("scope") != null
                    ? (List<String>) body.get("scope") : null;

            String subject = (String) body.get("subject");
            String capability = (String) body.get("capability");
            String parentToken = (String) body.get("parent_token");
            int ttlHours = body.get("ttl_hours") != null
                    ? ((Number) body.get("ttl_hours")).intValue() : 0;
            String callerClass = (String) body.get("caller_class");

            TokenRequest req = new TokenRequest(subject, scope, capability,
                    purposeParams, parentToken, ttlHours, callerClass);

            TokenResponse resp = service.issueToken(principal.get(), req);

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("issued", resp.isIssued());
            result.put("token_id", resp.getTokenId());
            result.put("token", resp.getToken());
            result.put("expires", resp.getExpires());
            return Response.ok(result).build();
        } catch (ANIPError e) {
            int status = Constants.failureStatusCode(e.getErrorType());
            return failureResponse(status, e);
        } catch (Exception e) {
            return failureResponse(500,
                    Constants.FAILURE_INTERNAL_ERROR, "Token issuance failed", false);
        }
    }

    // --- 5. Permissions (JWT auth) ---

    @POST
    @Path("anip/permissions")
    @Produces(MediaType.APPLICATION_JSON)
    public Response permissions(@HeaderParam("Authorization") String authHeader) {
        DelegationToken token = resolveJwt(authHeader);
        PermissionResponse resp = service.discoverPermissions(token);
        return Response.ok(toMap(resp)).build();
    }

    // --- 6. Invoke (JWT auth) ---

    @POST
    @Path("anip/invoke/{capability}")
    @Produces(MediaType.APPLICATION_JSON)
    public Response invoke(@PathParam("capability") String capability,
                           Map<String, Object> body,
                           @HeaderParam("Authorization") String authHeader,
                           @HeaderParam("X-Client-Reference-Id") String clientRefHeader) {
        DelegationToken token = resolveJwt(authHeader);

        Map<String, Object> params = new LinkedHashMap<>();
        if (body != null) {
            @SuppressWarnings("unchecked")
            Map<String, Object> p = (Map<String, Object>) body.get("parameters");
            if (p != null) {
                params = p;
            } else {
                // Use the body itself (minus control fields).
                params = new LinkedHashMap<>(body);
                params.remove("stream");
                params.remove("client_reference_id");
                params.remove("task_id");
                params.remove("parent_invocation_id");
            }
        }

        boolean stream = body != null && Boolean.TRUE.equals(body.get("stream"));
        String clientRefId = body != null ? (String) body.get("client_reference_id") : null;
        if (clientRefId == null) {
            clientRefId = clientRefHeader;
        }
        String taskId = body != null ? (String) body.get("task_id") : null;
        String parentInvId = body != null ? (String) body.get("parent_invocation_id") : null;

        if (stream) {
            InvokeOpts streamOpts = new InvokeOpts(clientRefId, true, taskId, parentInvId);
            return handleStreamInvoke(capability, token, params, streamOpts);
        }

        InvokeOpts opts = new InvokeOpts(clientRefId, false, taskId, parentInvId);
        Map<String, Object> result = service.invoke(capability, token, params, opts);

        boolean success = Boolean.TRUE.equals(result.get("success"));
        if (!success) {
            @SuppressWarnings("unchecked")
            Map<String, Object> failure = (Map<String, Object>) result.get("failure");
            String failType = failure != null ? (String) failure.get("type") : null;
            int statusCode = Constants.failureStatusCode(failType);
            return Response.status(statusCode).entity(result).build();
        }

        return Response.ok(result).build();
    }

    // --- 7. Audit (JWT auth) ---

    @POST
    @Path("anip/audit")
    @Consumes(MediaType.WILDCARD)
    @Produces(MediaType.APPLICATION_JSON)
    public Response audit(String rawBody,
                          @HeaderParam("Authorization") String authHeader,
                          @QueryParam("capability") String qCapability,
                          @QueryParam("since") String qSince,
                          @QueryParam("invocation_id") String qInvocationId,
                          @QueryParam("client_reference_id") String qClientReferenceId,
                          @QueryParam("task_id") String qTaskId,
                          @QueryParam("parent_invocation_id") String qParentInvId,
                          @QueryParam("limit") String qLimit) {
        DelegationToken token = resolveJwt(authHeader);

        try {
            // Parse body as JSON if present.
            @SuppressWarnings("unchecked")
            Map<String, Object> body = (rawBody != null && !rawBody.isBlank())
                    ? MAPPER.readValue(rawBody, Map.class) : null;

            // Read filters from body.
            String capability = body != null ? (String) body.get("capability") : null;
            String since = body != null ? (String) body.get("since") : null;
            String invocationId = body != null ? (String) body.get("invocation_id") : null;
            String clientReferenceId = body != null ? (String) body.get("client_reference_id") : null;
            int limit = body != null && body.get("limit") != null
                    ? ((Number) body.get("limit")).intValue() : 50;

            String taskId = body != null ? (String) body.get("task_id") : null;
            String parentInvId = body != null ? (String) body.get("parent_invocation_id") : null;

            // Query params override body.
            if (qCapability != null && !qCapability.isEmpty()) capability = qCapability;
            if (qSince != null && !qSince.isEmpty()) since = qSince;
            if (qInvocationId != null && !qInvocationId.isEmpty()) invocationId = qInvocationId;
            if (qClientReferenceId != null && !qClientReferenceId.isEmpty()) clientReferenceId = qClientReferenceId;
            if (qTaskId != null && !qTaskId.isEmpty()) taskId = qTaskId;
            if (qParentInvId != null && !qParentInvId.isEmpty()) parentInvId = qParentInvId;
            if (qLimit != null && !qLimit.isEmpty()) {
                try { limit = Integer.parseInt(qLimit); } catch (NumberFormatException ignored) {}
            }

            AuditFilters filters = new AuditFilters(capability, since, invocationId,
                    clientReferenceId, taskId, parentInvId, limit);
            AuditResponse resp = service.queryAudit(token, filters);
            return Response.ok(toMap(resp)).build();
        } catch (ANIPError e) {
            int status = Constants.failureStatusCode(e.getErrorType());
            return failureResponse(status, e);
        } catch (Exception e) {
            return failureResponse(500,
                    Constants.FAILURE_INTERNAL_ERROR, "Audit query failed", false);
        }
    }

    // --- 8. Checkpoints (no auth) ---

    @GET
    @Path("anip/checkpoints")
    @Produces(MediaType.APPLICATION_JSON)
    public Response listCheckpoints(@QueryParam("limit") Integer limitParam) {
        try {
            int limit = (limitParam != null) ? limitParam : 50;
            CheckpointListResponse resp = service.listCheckpoints(limit);
            return Response.ok(toMap(resp)).build();
        } catch (Exception e) {
            return failureResponse(500,
                    Constants.FAILURE_INTERNAL_ERROR, "Failed to list checkpoints", false);
        }
    }

    @GET
    @Path("anip/checkpoints/{id}")
    @Produces(MediaType.APPLICATION_JSON)
    public Response getCheckpoint(
            @PathParam("id") String id,
            @QueryParam("include_proof") Boolean includeProofParam,
            @QueryParam("leaf_index") Integer leafIndexParam) {
        try {
            boolean includeProof = includeProofParam != null && includeProofParam;
            int leafIndex = (leafIndexParam != null) ? leafIndexParam : 0;
            CheckpointDetailResponse resp = service.getCheckpoint(id, includeProof, leafIndex);
            return Response.ok(toMap(resp)).build();
        } catch (ANIPError e) {
            int status = Constants.failureStatusCode(e.getErrorType());
            return failureResponse(status, e);
        } catch (Exception e) {
            return failureResponse(500,
                    Constants.FAILURE_INTERNAL_ERROR, "Failed to get checkpoint", false);
        }
    }

    // --- 9. Health (optional) ---

    @GET
    @Path("-/health")
    @Produces(MediaType.APPLICATION_JSON)
    public Response health() {
        if (!healthEnabled) {
            return Response.status(404).build();
        }
        HealthReport report = service.getHealth();
        return Response.ok(toMap(report)).build();
    }

    // --- SSE streaming ---

    private Response handleStreamInvoke(String capability, DelegationToken token,
                                         Map<String, Object> params, InvokeOpts opts) {
        StreamResult sr;
        try {
            sr = service.invokeStream(capability, token, params, opts);
        } catch (ANIPError e) {
            // Return a single SSE error event then close.
            StreamingOutput errorOutput = output -> {
                Map<String, Object> errorData = new LinkedHashMap<>();
                errorData.put("success", false);
                errorData.put("failure", Map.of(
                        "type", e.getErrorType(),
                        "detail", e.getDetail(),
                        "retry", e.isRetry()
                ));
                String eventStr = "event: failed\ndata: " + MAPPER.writeValueAsString(errorData) + "\n\n";
                output.write(eventStr.getBytes(StandardCharsets.UTF_8));
                output.flush();
            };
            return Response.ok(errorOutput).type(MediaType.SERVER_SENT_EVENTS_TYPE).build();
        }

        StreamingOutput streamingOutput = output -> {
            try {
                while (true) {
                    StreamEvent event = sr.getEvents().poll(30, TimeUnit.SECONDS);
                    if (event == null) {
                        break; // timeout
                    }
                    if (StreamResult.DONE_TYPE.equals(event.getType())) {
                        break;
                    }
                    String eventStr = "event: " + event.getType() + "\ndata: "
                            + MAPPER.writeValueAsString(event.getPayload()) + "\n\n";
                    output.write(eventStr.getBytes(StandardCharsets.UTF_8));
                    output.flush();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                sr.getCancel().run();
            } catch (IOException e) {
                sr.getCancel().run();
                throw e;
            }
        };

        return Response.ok(streamingOutput).type(MediaType.SERVER_SENT_EVENTS_TYPE).build();
    }

    // --- Auth helpers ---

    private String extractBearer(String authHeader) {
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            return authHeader.substring(7).trim();
        }
        return null;
    }

    private DelegationToken resolveJwt(String authHeader) {
        String bearer = extractBearer(authHeader);
        if (bearer == null || bearer.isEmpty()) {
            throw new WebApplicationException(Response.status(401)
                    .entity(failureBody(Constants.FAILURE_AUTH_REQUIRED,
                            "Authorization header with Bearer token required"))
                    .type(MediaType.APPLICATION_JSON_TYPE).build());
        }
        try {
            return service.resolveBearerToken(bearer);
        } catch (ANIPError e) {
            int status = Constants.failureStatusCode(e.getErrorType());
            throw new WebApplicationException(Response.status(status)
                    .entity(failureBody(e))
                    .type(MediaType.APPLICATION_JSON_TYPE).build());
        } catch (Exception e) {
            throw new WebApplicationException(Response.status(401)
                    .entity(failureBody(Constants.FAILURE_INVALID_TOKEN,
                            "Invalid bearer token"))
                    .type(MediaType.APPLICATION_JSON_TYPE).build());
        }
    }

    // --- Response helpers ---

    private String deriveBaseUrl(UriInfo uriInfo) {
        URI requestUri = uriInfo.getRequestUri();
        String scheme = requestUri.getScheme();
        String host = requestUri.getHost();
        int port = requestUri.getPort();
        if (port > 0 && port != 80 && port != 443) {
            return scheme + "://" + host + ":" + port;
        }
        return scheme + "://" + host;
    }

    private Response authRequiredResponse() {
        Map<String, Object> failure = new LinkedHashMap<>();
        failure.put("type", Constants.FAILURE_AUTH_REQUIRED);
        failure.put("detail", "Authorization header with Bearer token required");
        failure.put("resolution", Map.of(
                "action", "provide_credentials",
                "requires", "Bearer token"
        ));
        failure.put("retry", true);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("success", false);
        body.put("failure", failure);
        return Response.status(401).entity(body).type(MediaType.APPLICATION_JSON_TYPE).build();
    }

    private Response failureResponse(int status, String type, String detail, boolean retry) {
        Map<String, Object> body = failureBody(type, detail);
        @SuppressWarnings("unchecked")
        Map<String, Object> failure = (Map<String, Object>) body.get("failure");
        failure.put("resolution", defaultResolution(type));
        failure.put("retry", retry);
        return Response.status(status).entity(body).type(MediaType.APPLICATION_JSON_TYPE).build();
    }

    private Response failureResponse(int status, ANIPError e) {
        Map<String, Object> body = failureBody(e);
        return Response.status(status).entity(body).type(MediaType.APPLICATION_JSON_TYPE).build();
    }

    private Map<String, Object> failureBody(String type, String detail) {
        Map<String, Object> failure = new LinkedHashMap<>();
        failure.put("type", type);
        failure.put("detail", detail);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("success", false);
        body.put("failure", failure);
        return body;
    }

    private Map<String, Object> failureBody(ANIPError e) {
        Map<String, Object> failure = new LinkedHashMap<>();
        failure.put("type", e.getErrorType());
        failure.put("detail", e.getDetail());
        if (e.getResolution() != null) {
            Map<String, Object> res = new LinkedHashMap<>();
            res.put("action", e.getResolution().getAction());
            if (e.getResolution().getRequires() != null) {
                res.put("requires", e.getResolution().getRequires());
            }
            if (e.getResolution().getGrantableBy() != null) {
                res.put("grantable_by", e.getResolution().getGrantableBy());
            }
            failure.put("resolution", res);
        } else {
            failure.put("resolution", defaultResolution(e.getErrorType()));
        }
        failure.put("retry", e.isRetry());

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("success", false);
        body.put("failure", failure);
        return body;
    }

    private Map<String, Object> defaultResolution(String failureType) {
        return switch (failureType) {
            case Constants.FAILURE_AUTH_REQUIRED -> Map.of(
                    "action", "provide_credentials",
                    "requires", "Bearer token"
            );
            case Constants.FAILURE_INVALID_TOKEN, Constants.FAILURE_TOKEN_EXPIRED -> Map.of(
                    "action", "reauthenticate"
            );
            case Constants.FAILURE_SCOPE_INSUFFICIENT -> Map.of(
                    "action", "request_scope"
            );
            case Constants.FAILURE_BUDGET_EXCEEDED -> Map.of(
                    "action", "request_budget_increase"
            );
            default -> Map.of("action", "contact_administrator");
        };
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> toMap(Object obj) {
        return MAPPER.convertValue(obj, Map.class);
    }
}
