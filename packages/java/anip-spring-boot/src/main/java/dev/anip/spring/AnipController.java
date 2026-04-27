package dev.anip.spring;

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

import jakarta.servlet.http.HttpServletRequest;

import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.TimeUnit;

/**
 * Spring MVC controller implementing all 9 ANIP protocol routes plus health.
 */
@RestController
public class AnipController {

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
            .setSerializationInclusion(JsonInclude.Include.NON_NULL)
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
            .configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);

    private final ANIPService service;
    private final boolean healthEnabled;

    public AnipController(ANIPService service) {
        this(service, true);
    }

    public AnipController(ANIPService service, boolean healthEnabled) {
        this.service = service;
        this.healthEnabled = healthEnabled;
    }

    // --- 1. Discovery ---

    @GetMapping(value = "/.well-known/anip", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> discovery(HttpServletRequest request) {
        String baseUrl = deriveBaseUrl(request);
        Map<String, Object> doc = service.getDiscovery(baseUrl);
        return ResponseEntity.ok(doc);
    }

    // --- 2. JWKS ---

    @GetMapping(value = "/.well-known/jwks.json", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> jwks() {
        return ResponseEntity.ok(service.getJwks());
    }

    // --- 3. Manifest ---

    @GetMapping(value = "/anip/manifest", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<byte[]> manifest() {
        SignedManifest sm = service.getSignedManifest();
        return ResponseEntity.ok()
                .header("X-ANIP-Signature", sm.getSignature())
                .contentType(MediaType.APPLICATION_JSON)
                .body(sm.getManifestJson());
    }

    // --- 4. Token issuance (bootstrap auth only) ---

    @PostMapping(value = "/anip/tokens", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> issueToken(@RequestBody Map<String, Object> body,
                                              HttpServletRequest request) {
        String bearer = extractBearer(request);
        if (bearer == null || bearer.isEmpty()) {
            return authRequiredResponse();
        }

        // Bootstrap auth only.
        Optional<String> principal = service.authenticateBearer(bearer);
        if (principal.isEmpty()) {
            return failureResponse(HttpStatus.UNAUTHORIZED, Constants.FAILURE_INVALID_TOKEN,
                    "Invalid bootstrap credential", true);
        }

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> purposeParams = (Map<String, Object>) body.get("purpose_parameters");

            @SuppressWarnings("unchecked")
            java.util.List<String> scope = body.get("scope") != null
                    ? (java.util.List<String>) body.get("scope") : null;

            String subject = (String) body.get("subject");
            String capability = (String) body.get("capability");
            String parentToken = (String) body.get("parent_token");
            int ttlHours = body.get("ttl_hours") != null
                    ? ((Number) body.get("ttl_hours")).intValue() : 0;
            String callerClass = (String) body.get("caller_class");
            String concurrentBranches = (String) body.get("concurrent_branches");
            // v0.23: bind a session identity into the issued token so the
            // caller can later redeem session_bound ApprovalGrants. SPEC §4.8.
            String sessionId = (String) body.get("session_id");

            dev.anip.core.Budget tokenBudget = extractBudget(body);
            TokenRequest req = new TokenRequest(subject, scope, capability,
                    purposeParams, parentToken, ttlHours, callerClass, tokenBudget,
                    concurrentBranches, sessionId);

            TokenResponse resp = service.issueToken(principal.get(), req);

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("issued", resp.isIssued());
            result.put("token_id", resp.getTokenId());
            result.put("token", resp.getToken());
            result.put("expires", resp.getExpires());
            if (resp.getTaskId() != null) {
                result.put("task_id", resp.getTaskId());
            }
            return ResponseEntity.ok(result);
        } catch (ANIPError e) {
            int status = Constants.failureStatusCode(e.getErrorType());
            return failureResponse(HttpStatus.valueOf(status), e);
        } catch (Exception e) {
            return failureResponse(HttpStatus.INTERNAL_SERVER_ERROR,
                    Constants.FAILURE_INTERNAL_ERROR, "Token issuance failed", false);
        }
    }

    // --- 5. Permissions (JWT auth) ---

    @PostMapping(value = "/anip/permissions", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> permissions(HttpServletRequest request) {
        DelegationToken token;
        try {
            token = resolveJwtAuth(request);
        } catch (ResponseException re) {
            return re.toResponse();
        }

        PermissionResponse resp = service.discoverPermissions(token);
        return ResponseEntity.ok(toMap(resp));
    }

    // --- 6. Invoke (JWT auth) ---

    @PostMapping(value = "/anip/invoke/{capability}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Object invoke(@PathVariable String capability,
                          @RequestBody(required = false) Map<String, Object> body,
                          HttpServletRequest request) {
        DelegationToken token;
        try {
            token = resolveJwtAuth(request);
        } catch (ResponseException re) {
            return re.toResponse();
        }

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
                params.remove("upstream_service");
                params.remove("budget");
                // v0.23: strip approval_grant so it does not leak into the
                // params digest. Otherwise continuation validation hashes the
                // grant id as a business parameter and fails grant_param_drift.
                params.remove("approval_grant");
            }
        }

        boolean stream = body != null && Boolean.TRUE.equals(body.get("stream"));
        String clientRefId = body != null ? (String) body.get("client_reference_id") : null;
        if (clientRefId == null) {
            clientRefId = request.getHeader("X-Client-Reference-Id");
        }
        String taskId = body != null ? (String) body.get("task_id") : null;
        String parentInvocationId = body != null ? (String) body.get("parent_invocation_id") : null;
        String upstreamService = body != null ? (String) body.get("upstream_service") : null;
        // v0.23: continuation invocations supply approval_grant. session_id
        // for session_bound grants is read from the signed token, never the body.
        String approvalGrant = body != null ? (String) body.get("approval_grant") : null;

        // Extract budget from request body.
        dev.anip.core.Budget budget = extractBudget(body);

        if (stream) {
            return handleStreamInvoke(capability, token, params, clientRefId, taskId,
                    parentInvocationId, upstreamService, budget, approvalGrant);
        }

        InvokeOpts opts = new InvokeOpts(clientRefId, false, taskId, parentInvocationId, upstreamService);
        if (budget != null) opts.setBudget(budget);
        if (approvalGrant != null) opts.setApprovalGrant(approvalGrant);
        Map<String, Object> result = service.invoke(capability, token, params, opts);

        boolean success = Boolean.TRUE.equals(result.get("success"));
        if (!success) {
            @SuppressWarnings("unchecked")
            Map<String, Object> failure = (Map<String, Object>) result.get("failure");
            String failType = failure != null ? (String) failure.get("type") : null;
            int statusCode = Constants.failureStatusCode(failType);
            return ResponseEntity.status(statusCode).body(result);
        }

        return ResponseEntity.ok(result);
    }

    // --- 7. Audit (JWT auth) ---

    @PostMapping(value = "/anip/audit", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> audit(@RequestBody(required = false) Map<String, Object> body,
                                         HttpServletRequest request) {
        DelegationToken token;
        try {
            token = resolveJwtAuth(request);
        } catch (ResponseException re) {
            return re.toResponse();
        }

        try {
            // Read filters from body and/or query params (query params take precedence).
            String capability = body != null ? (String) body.get("capability") : null;
            String since = body != null ? (String) body.get("since") : null;
            String invocationId = body != null ? (String) body.get("invocation_id") : null;
            String clientReferenceId = body != null ? (String) body.get("client_reference_id") : null;
            String taskId = body != null ? (String) body.get("task_id") : null;
            String parentInvocationId = body != null ? (String) body.get("parent_invocation_id") : null;
            int limit = body != null && body.get("limit") != null
                    ? ((Number) body.get("limit")).intValue() : 50;

            // Query params override body.
            String qCapability = request.getParameter("capability");
            if (qCapability != null && !qCapability.isEmpty()) capability = qCapability;
            String qSince = request.getParameter("since");
            if (qSince != null && !qSince.isEmpty()) since = qSince;
            String qInvocationId = request.getParameter("invocation_id");
            if (qInvocationId != null && !qInvocationId.isEmpty()) invocationId = qInvocationId;
            String qClientReferenceId = request.getParameter("client_reference_id");
            if (qClientReferenceId != null && !qClientReferenceId.isEmpty()) clientReferenceId = qClientReferenceId;
            String qTaskId = request.getParameter("task_id");
            if (qTaskId != null && !qTaskId.isEmpty()) taskId = qTaskId;
            String qParentInvocationId = request.getParameter("parent_invocation_id");
            if (qParentInvocationId != null && !qParentInvocationId.isEmpty()) parentInvocationId = qParentInvocationId;
            String qLimit = request.getParameter("limit");
            if (qLimit != null && !qLimit.isEmpty()) {
                try { limit = Integer.parseInt(qLimit); } catch (NumberFormatException ignored) {}
            }

            AuditFilters filters = new AuditFilters(capability, null, since, invocationId,
                    clientReferenceId, taskId, parentInvocationId, limit);
            AuditResponse resp = service.queryAudit(token, filters);
            return ResponseEntity.ok(toMap(resp));
        } catch (ANIPError e) {
            int status = Constants.failureStatusCode(e.getErrorType());
            return failureResponse(HttpStatus.valueOf(status), e);
        } catch (Exception e) {
            return failureResponse(HttpStatus.INTERNAL_SERVER_ERROR,
                    Constants.FAILURE_INTERNAL_ERROR, "Audit query failed", false);
        }
    }

    // --- Graph (no auth) ---

    @GetMapping(value = "/anip/graph/{capability}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> graph(@PathVariable String capability) {
        Map<String, Object> graph = service.getCapabilityGraph(capability);
        if (graph == null) {
            return failureResponse(HttpStatus.NOT_FOUND, Constants.FAILURE_NOT_FOUND,
                    "Capability '" + capability + "' not found", false);
        }
        return ResponseEntity.ok(graph);
    }

    // --- 8. Checkpoints (no auth) ---

    @GetMapping(value = "/anip/checkpoints", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> listCheckpoints(
            @RequestParam(value = "limit", defaultValue = "50") int limit) {
        try {
            CheckpointListResponse resp = service.listCheckpoints(limit);
            return ResponseEntity.ok(toMap(resp));
        } catch (Exception e) {
            return failureResponse(HttpStatus.INTERNAL_SERVER_ERROR,
                    Constants.FAILURE_INTERNAL_ERROR, "Failed to list checkpoints", false);
        }
    }

    @GetMapping(value = "/anip/checkpoints/{id}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> getCheckpoint(
            @PathVariable String id,
            @RequestParam(value = "include_proof", defaultValue = "false") boolean includeProof,
            @RequestParam(value = "leaf_index", defaultValue = "0") int leafIndex) {
        try {
            CheckpointDetailResponse resp = service.getCheckpoint(id, includeProof, leafIndex);
            return ResponseEntity.ok(toMap(resp));
        } catch (ANIPError e) {
            int status = Constants.failureStatusCode(e.getErrorType());
            return failureResponse(HttpStatus.valueOf(status), e);
        } catch (Exception e) {
            return failureResponse(HttpStatus.INTERNAL_SERVER_ERROR,
                    Constants.FAILURE_INTERNAL_ERROR, "Failed to get checkpoint", false);
        }
    }

    // --- 9. Health (optional) ---

    @GetMapping(value = "/-/health", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> health() {
        if (!healthEnabled) {
            return ResponseEntity.notFound().build();
        }
        HealthReport report = service.getHealth();
        return ResponseEntity.ok(toMap(report));
    }

    // --- SSE streaming ---

    private SseEmitter handleStreamInvoke(String capability, DelegationToken token,
                                           Map<String, Object> params, String clientRefId,
                                           String taskId, String parentInvocationId,
                                           String upstreamService, dev.anip.core.Budget budget,
                                           String approvalGrant) {
        SseEmitter emitter = new SseEmitter(0L); // no timeout

        StreamResult sr;
        try {
            InvokeOpts opts = new InvokeOpts(clientRefId, true, taskId, parentInvocationId, upstreamService);
            if (budget != null) opts.setBudget(budget);
            if (approvalGrant != null) opts.setApprovalGrant(approvalGrant);
            sr = service.invokeStream(capability, token, params, opts);
        } catch (ANIPError e) {
            try {
                Map<String, Object> errorData = new LinkedHashMap<>();
                errorData.put("success", false);
                errorData.put("failure", Map.of(
                        "type", e.getErrorType(),
                        "detail", e.getDetail(),
                        "retry", e.isRetry()
                ));
                emitter.send(SseEmitter.event().name("failed").data(errorData));
                emitter.complete();
            } catch (Exception ignored) {
                emitter.completeWithError(e);
            }
            return emitter;
        }

        // Emit on disconnect: cancel the stream.
        emitter.onCompletion(sr.getCancel());
        emitter.onTimeout(sr.getCancel());
        emitter.onError(t -> sr.getCancel().run());

        // Reader thread: pull events from queue and send as SSE.
        Thread reader = new Thread(() -> {
            try {
                while (true) {
                    StreamEvent event = sr.getEvents().poll(30, TimeUnit.SECONDS);
                    if (event == null) {
                        break; // timeout
                    }
                    if (StreamResult.DONE_TYPE.equals(event.getType())) {
                        break;
                    }
                    emitter.send(SseEmitter.event()
                            .name(event.getType())
                            .data(event.getPayload()));
                }
                emitter.complete();
            } catch (Exception e) {
                sr.getCancel().run();
                emitter.completeWithError(e);
            }
        }, "anip-sse-reader");
        reader.setDaemon(true);
        reader.start();

        return emitter;
    }

    // --- Auth helpers ---

    /**
     * Extracts bearer from Authorization header. Returns null if not present.
     */
    @SuppressWarnings("unchecked")
    private dev.anip.core.Budget extractBudget(Map<String, Object> body) {
        if (body == null) return null;
        Object budgetRaw = body.get("budget");
        if (!(budgetRaw instanceof Map)) return null;
        Map<String, Object> budgetMap = (Map<String, Object>) budgetRaw;
        String currency = budgetMap.get("currency") instanceof String s ? s : null;
        double maxAmount = budgetMap.get("max_amount") instanceof Number n ? n.doubleValue() : 0;
        if (currency != null && !currency.isEmpty() && maxAmount > 0) {
            return new dev.anip.core.Budget(currency, maxAmount);
        }
        return null;
    }

    private String extractBearer(HttpServletRequest request) {
        String auth = request.getHeader("Authorization");
        if (auth != null && auth.startsWith("Bearer ")) {
            return auth.substring(7).trim();
        }
        return null;
    }

    /**
     * Resolves ANIP JWT from the request. Protected routes: JWT only, no API key fallback.
     */
    private DelegationToken resolveJwtAuth(HttpServletRequest request) throws ResponseException {
        String bearer = extractBearer(request);
        if (bearer == null || bearer.isEmpty()) {
            throw new ResponseException(authRequiredResponse());
        }

        try {
            return service.resolveBearerToken(bearer);
        } catch (ANIPError e) {
            int status = Constants.failureStatusCode(e.getErrorType());
            throw new ResponseException(failureResponse(HttpStatus.valueOf(status), e));
        } catch (Exception e) {
            throw new ResponseException(failureResponse(HttpStatus.UNAUTHORIZED,
                    Constants.FAILURE_INVALID_TOKEN, "Invalid bearer token", false));
        }
    }

    // --- Response helpers ---

    private String deriveBaseUrl(HttpServletRequest request) {
        String scheme = request.getScheme();
        String host = request.getServerName();
        int port = request.getServerPort();

        // Check for forwarded headers.
        String forwardedProto = request.getHeader("X-Forwarded-Proto");
        if (forwardedProto != null) {
            scheme = forwardedProto;
        }
        String forwardedHost = request.getHeader("X-Forwarded-Host");
        if (forwardedHost != null) {
            host = forwardedHost;
            port = -1; // port included in host
        }

        StringBuilder sb = new StringBuilder(scheme).append("://").append(host);
        if (port > 0 && port != 80 && port != 443) {
            sb.append(":").append(port);
        }
        return sb.toString();
    }

    private ResponseEntity<Object> authRequiredResponse() {
        Map<String, Object> failure = new LinkedHashMap<>();
        failure.put("type", Constants.FAILURE_AUTH_REQUIRED);
        failure.put("detail", "Authorization header with Bearer token required");
        Map<String, Object> resolution = new LinkedHashMap<>();
        resolution.put("action", "provide_credentials");
        resolution.put("recovery_class", Constants.recoveryClassForAction("provide_credentials"));
        resolution.put("requires", "Bearer token");
        failure.put("resolution", resolution);
        failure.put("retry", true);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("success", false);
        body.put("failure", failure);
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(body);
    }

    private ResponseEntity<Object> failureResponse(HttpStatus status, String type,
                                                     String detail, boolean retry) {
        Map<String, Object> failure = new LinkedHashMap<>();
        failure.put("type", type);
        failure.put("detail", detail);
        failure.put("resolution", defaultResolution(type));
        failure.put("retry", retry);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("success", false);
        body.put("failure", failure);
        return ResponseEntity.status(status).body(body);
    }

    private ResponseEntity<Object> failureResponse(HttpStatus status, ANIPError e) {
        Map<String, Object> failure = new LinkedHashMap<>();
        failure.put("type", e.getErrorType());
        failure.put("detail", e.getDetail());
        if (e.getResolution() != null) {
            Map<String, Object> res = new LinkedHashMap<>();
            res.put("action", e.getResolution().getAction());
            res.put("recovery_class", e.getResolution().getRecoveryClass());
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
        return ResponseEntity.status(status).body(body);
    }

    private Map<String, Object> defaultResolution(String failureType) {
        return switch (failureType) {
            case Constants.FAILURE_AUTH_REQUIRED -> Map.of(
                    "action", "provide_credentials",
                    "recovery_class", Constants.recoveryClassForAction("provide_credentials"),
                    "requires", "Bearer token"
            );
            case Constants.FAILURE_INVALID_TOKEN, Constants.FAILURE_TOKEN_EXPIRED -> Map.of(
                    "action", "request_new_delegation",
                    "recovery_class", Constants.recoveryClassForAction("request_new_delegation")
            );
            case Constants.FAILURE_SCOPE_INSUFFICIENT -> Map.of(
                    "action", "request_broader_scope",
                    "recovery_class", Constants.recoveryClassForAction("request_broader_scope")
            );
            case Constants.FAILURE_BUDGET_EXCEEDED -> Map.of(
                    "action", "request_budget_increase",
                    "recovery_class", Constants.recoveryClassForAction("request_budget_increase")
            );
            default -> Map.of(
                    "action", "contact_service_owner",
                    "recovery_class", Constants.recoveryClassForAction("contact_service_owner")
            );
        };
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> toMap(Object obj) {
        return MAPPER.convertValue(obj, Map.class);
    }

    /**
     * Internal exception to short-circuit auth failure in controller methods.
     */
    private static class ResponseException extends Exception {
        private final ResponseEntity<Object> response;

        ResponseException(ResponseEntity<Object> response) {
            this.response = response;
        }

        ResponseEntity<Object> toResponse() {
            return response;
        }
    }
}
