package dev.anip.stdio;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.SerializationFeature;

import dev.anip.core.ANIPError;
import dev.anip.core.AuditFilters;
import dev.anip.core.AuditResponse;
import dev.anip.core.CheckpointDetailResponse;
import dev.anip.core.CheckpointListResponse;
import dev.anip.core.DelegationToken;
import dev.anip.core.PermissionResponse;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.service.ANIPService;
import dev.anip.service.InvokeOpts;
import dev.anip.service.SignedManifest;
import dev.anip.service.StreamEvent;
import dev.anip.service.StreamResult;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.TimeUnit;

/**
 * JSON-RPC 2.0 server wrapping an ANIPService for stdio transport.
 *
 * <p>Reads newline-delimited JSON from an input stream, dispatches each
 * request to the appropriate ANIP method handler, and writes newline-delimited
 * JSON responses to an output stream.</p>
 */
public class AnipStdioServer {

    // --- JSON-RPC 2.0 error codes ---

    static final int PARSE_ERROR = -32700;
    static final int INVALID_REQUEST = -32600;
    static final int METHOD_NOT_FOUND = -32601;
    static final int INTERNAL_ERROR = -32603;
    static final int AUTH_ERROR = -32001;
    static final int SCOPE_ERROR = -32002;
    static final int NOT_FOUND_ERROR = -32004;

    // --- ANIP failure type to JSON-RPC error code mapping ---

    private static final Map<String, Integer> FAILURE_TYPE_TO_CODE = Map.ofEntries(
            Map.entry("authentication_required", AUTH_ERROR),
            Map.entry("invalid_token", AUTH_ERROR),
            Map.entry("token_expired", AUTH_ERROR),
            Map.entry("scope_insufficient", SCOPE_ERROR),
            Map.entry("budget_exceeded", SCOPE_ERROR),
            Map.entry("purpose_mismatch", SCOPE_ERROR),
            Map.entry("unknown_capability", NOT_FOUND_ERROR),
            Map.entry("not_found", NOT_FOUND_ERROR),
            Map.entry("internal_error", INTERNAL_ERROR),
            Map.entry("unavailable", INTERNAL_ERROR),
            Map.entry("concurrent_lock", INTERNAL_ERROR)
    );

    private static final Set<String> VALID_METHODS = Set.of(
            "anip.discovery",
            "anip.manifest",
            "anip.jwks",
            "anip.tokens.issue",
            "anip.permissions",
            "anip.invoke",
            "anip.audit.query",
            "anip.checkpoints.list",
            "anip.checkpoints.get"
    );

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
            .setSerializationInclusion(JsonInclude.Include.NON_NULL)
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
            .configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);

    private final ANIPService service;

    /**
     * Creates a new stdio server backed by the given ANIP service.
     *
     * @param service the ANIP service to dispatch requests to
     */
    public AnipStdioServer(ANIPService service) {
        this.service = service;
    }

    // --- Public serve methods ---

    /**
     * Convenience method that serves on {@code System.in} / {@code System.out}.
     */
    public void serve() throws IOException {
        serve(System.in, System.out);
    }

    /**
     * Main loop: read newline-delimited JSON-RPC from {@code in}, dispatch,
     * and write responses to {@code out}.
     */
    public void serve(InputStream in, OutputStream out) throws IOException {
        BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8));
        String line;
        while ((line = reader.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty()) {
                continue;
            }

            Map<String, Object> msg;
            try {
                @SuppressWarnings("unchecked")
                Map<String, Object> parsed = MAPPER.readValue(line, Map.class);
                msg = parsed;
            } catch (JsonProcessingException e) {
                Map<String, Object> errorResp = makeError(null, PARSE_ERROR,
                        "Parse error: " + e.getOriginalMessage());
                writeLine(out, errorResp);
                continue;
            }

            Object result = handleRequest(msg);

            if (result instanceof List) {
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> messages = (List<Map<String, Object>>) result;
                for (Map<String, Object> item : messages) {
                    writeLine(out, item);
                }
            } else {
                @SuppressWarnings("unchecked")
                Map<String, Object> response = (Map<String, Object>) result;
                writeLine(out, response);
            }
        }
    }

    // --- Public dispatch ---

    /**
     * Validates and dispatches a JSON-RPC request to the appropriate handler.
     *
     * @param msg the parsed JSON-RPC request
     * @return a single JSON-RPC response map, or for streaming invocations
     *         a list of [notification..., response]
     */
    public Object handleRequest(Map<String, Object> msg) {
        String validationError = validateRequest(msg);
        if (validationError != null) {
            return makeError(getRequestId(msg), INVALID_REQUEST, validationError);
        }

        Object requestId = msg.get("id");
        String method = (String) msg.get("method");

        @SuppressWarnings("unchecked")
        Map<String, Object> params = msg.get("params") instanceof Map
                ? (Map<String, Object>) msg.get("params")
                : Map.of();

        if (!VALID_METHODS.contains(method)) {
            return makeError(requestId, METHOD_NOT_FOUND, "Unknown method: " + method);
        }

        try {
            Object result = dispatch(method, params);

            // Streaming invoke returns a two-element list: [notifications, finalResult].
            if (result instanceof Object[] arr && arr.length == 2) {
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> notifications = (List<Map<String, Object>>) arr[0];
                @SuppressWarnings("unchecked")
                Map<String, Object> finalResult = (Map<String, Object>) arr[1];
                List<Map<String, Object>> messages = new ArrayList<>(notifications);
                messages.add(makeResponse(requestId, finalResult));
                return messages;
            }

            @SuppressWarnings("unchecked")
            Map<String, Object> resultMap = (Map<String, Object>) result;
            return makeResponse(requestId, resultMap);
        } catch (ANIPError e) {
            int code = FAILURE_TYPE_TO_CODE.getOrDefault(e.getErrorType(), INTERNAL_ERROR);
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("type", e.getErrorType());
            data.put("detail", e.getDetail());
            data.put("retry", e.isRetry());
            return makeError(requestId, code, e.getDetail(), data);
        } catch (Exception e) {
            return makeError(requestId, INTERNAL_ERROR, e.getMessage());
        }
    }

    // --- Method dispatch ---

    private Object dispatch(String method, Map<String, Object> params) throws Exception {
        return switch (method) {
            case "anip.discovery" -> handleDiscovery(params);
            case "anip.manifest" -> handleManifest(params);
            case "anip.jwks" -> handleJwks(params);
            case "anip.tokens.issue" -> handleTokensIssue(params);
            case "anip.permissions" -> handlePermissions(params);
            case "anip.invoke" -> handleInvoke(params);
            case "anip.audit.query" -> handleAuditQuery(params);
            case "anip.checkpoints.list" -> handleCheckpointsList(params);
            case "anip.checkpoints.get" -> handleCheckpointsGet(params);
            default -> throw new IllegalStateException("Unhandled method: " + method);
        };
    }

    // --- Method handlers ---

    private Map<String, Object> handleDiscovery(Map<String, Object> params) {
        return service.getDiscovery(null);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> handleManifest(Map<String, Object> params) throws Exception {
        SignedManifest sm = service.getSignedManifest();
        Map<String, Object> manifest = MAPPER.readValue(sm.getManifestJson(), Map.class);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("manifest", manifest);
        result.put("signature", sm.getSignature());
        return result;
    }

    private Map<String, Object> handleJwks(Map<String, Object> params) {
        return service.getJwks();
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> handleTokensIssue(Map<String, Object> params) throws Exception {
        String bearer = extractAuth(params);
        if (bearer == null) {
            throw new ANIPError("authentication_required", "This method requires auth.bearer");
        }

        // Try bootstrap auth (API key) first, then ANIP JWT.
        Optional<String> principal = service.authenticateBearer(bearer);
        if (principal.isEmpty()) {
            throw new ANIPError("invalid_token", "Bearer token not recognized");
        }

        // Build the token request from params.
        String subject = (String) params.get("subject");
        List<String> scope = params.get("scope") instanceof List
                ? (List<String>) params.get("scope") : null;
        String capability = (String) params.get("capability");
        Map<String, Object> purposeParameters = params.get("purpose_parameters") instanceof Map
                ? (Map<String, Object>) params.get("purpose_parameters") : null;
        String parentToken = (String) params.get("parent_token");
        int ttlHours = params.get("ttl_hours") instanceof Number
                ? ((Number) params.get("ttl_hours")).intValue() : 0;
        String callerClass = (String) params.get("caller_class");

        TokenRequest req = new TokenRequest(
                subject, scope, capability, purposeParameters,
                parentToken, ttlHours, callerClass
        );

        TokenResponse resp = service.issueToken(principal.get(), req);
        return MAPPER.convertValue(resp, Map.class);
    }

    private Map<String, Object> handlePermissions(Map<String, Object> params) throws Exception {
        DelegationToken token = resolveJwt(params);
        PermissionResponse perm = service.discoverPermissions(token);
        @SuppressWarnings("unchecked")
        Map<String, Object> result = MAPPER.convertValue(perm, Map.class);
        return result;
    }

    @SuppressWarnings("unchecked")
    private Object handleInvoke(Map<String, Object> params) throws Exception {
        DelegationToken token = resolveJwt(params);

        String capability = (String) params.get("capability");
        if (capability == null || capability.isEmpty()) {
            throw new ANIPError("unknown_capability", "Missing 'capability' in params");
        }

        Map<String, Object> parameters = params.get("parameters") instanceof Map
                ? (Map<String, Object>) params.get("parameters") : Map.of();
        String clientReferenceId = (String) params.get("client_reference_id");
        boolean stream = Boolean.TRUE.equals(params.get("stream"));

        InvokeOpts opts = new InvokeOpts(clientReferenceId, stream);

        if (stream) {
            // Streaming invocation: collect progress notifications then return final result.
            StreamResult sr = service.invokeStream(capability, token, parameters, opts);
            BlockingQueue<StreamEvent> events = sr.getEvents();

            List<Map<String, Object>> notifications = new ArrayList<>();
            Map<String, Object> finalResult = null;

            while (true) {
                StreamEvent event = events.poll(30, TimeUnit.SECONDS);
                if (event == null) {
                    // Timeout waiting for events — cancel and break.
                    sr.getCancel().run();
                    break;
                }

                String eventType = event.getType();
                if (StreamResult.DONE_TYPE.equals(eventType)) {
                    break;
                }

                switch (eventType) {
                    case "progress":
                        notifications.add(
                                makeNotification("anip.invoke.progress", event.getPayload()));
                        break;
                    case "completed", "failed":
                        finalResult = event.getPayload();
                        break;
                }
            }

            if (finalResult == null) {
                finalResult = Map.of("success", false,
                        "failure", Map.of("type", "internal_error",
                                "detail", "Stream ended without terminal event"));
            }

            return new Object[] { notifications, finalResult };
        }

        // Unary invocation.
        Map<String, Object> result = service.invoke(capability, token, parameters, opts);
        return result;
    }

    private Map<String, Object> handleAuditQuery(Map<String, Object> params) throws Exception {
        DelegationToken token = resolveJwt(params);

        String capability = (String) params.get("capability");
        String since = (String) params.get("since");
        String invocationId = (String) params.get("invocation_id");
        String clientReferenceId = (String) params.get("client_reference_id");
        int limit = params.get("limit") instanceof Number
                ? ((Number) params.get("limit")).intValue() : 0;

        AuditFilters filters = new AuditFilters(capability, since, invocationId,
                clientReferenceId, limit);

        AuditResponse resp = service.queryAudit(token, filters);
        @SuppressWarnings("unchecked")
        Map<String, Object> result = MAPPER.convertValue(resp, Map.class);
        return result;
    }

    private Map<String, Object> handleCheckpointsList(Map<String, Object> params) throws Exception {
        int limit = params.get("limit") instanceof Number
                ? ((Number) params.get("limit")).intValue() : 10;

        CheckpointListResponse resp = service.listCheckpoints(limit);
        @SuppressWarnings("unchecked")
        Map<String, Object> result = MAPPER.convertValue(resp, Map.class);
        return result;
    }

    private Map<String, Object> handleCheckpointsGet(Map<String, Object> params) throws Exception {
        String id = (String) params.get("id");
        if (id == null || id.isEmpty()) {
            throw new ANIPError("not_found", "Missing 'id' in params");
        }

        boolean includeProof = Boolean.TRUE.equals(params.get("include_proof"));
        int leafIndex = params.get("leaf_index") instanceof Number
                ? ((Number) params.get("leaf_index")).intValue() : 0;

        CheckpointDetailResponse resp = service.getCheckpoint(id, includeProof, leafIndex);
        @SuppressWarnings("unchecked")
        Map<String, Object> result = MAPPER.convertValue(resp, Map.class);
        return result;
    }

    // --- Internal helpers ---

    private DelegationToken resolveJwt(Map<String, Object> params) throws Exception {
        String bearer = extractAuth(params);
        if (bearer == null) {
            throw new ANIPError("authentication_required", "This method requires auth.bearer");
        }
        return service.resolveBearerToken(bearer);
    }

    @SuppressWarnings("unchecked")
    public static String extractAuth(Map<String, Object> params) {
        if (params == null) {
            return null;
        }
        Object auth = params.get("auth");
        if (!(auth instanceof Map)) {
            return null;
        }
        Object bearer = ((Map<String, Object>) auth).get("bearer");
        return bearer instanceof String ? (String) bearer : null;
    }

    // --- Request validation ---

    static String validateRequest(Map<String, Object> msg) {
        if (msg == null) {
            return "Request must be a JSON object";
        }
        if (!"2.0".equals(msg.get("jsonrpc"))) {
            return "Missing or invalid 'jsonrpc' field (must be '2.0')";
        }
        if (!msg.containsKey("method")) {
            return "Missing 'method' field";
        }
        if (!(msg.get("method") instanceof String)) {
            return "'method' must be a string";
        }
        if (!msg.containsKey("id")) {
            return "Missing 'id' field (notifications not supported as requests)";
        }
        return null;
    }

    // --- JSON-RPC message constructors ---

    static Map<String, Object> makeResponse(Object requestId, Object result) {
        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("jsonrpc", "2.0");
        resp.put("id", requestId);
        resp.put("result", result);
        return resp;
    }

    static Map<String, Object> makeError(Object requestId, int code, String message) {
        return makeError(requestId, code, message, null);
    }

    static Map<String, Object> makeError(Object requestId, int code, String message,
                                          Map<String, Object> data) {
        Map<String, Object> error = new LinkedHashMap<>();
        error.put("code", code);
        error.put("message", message);
        if (data != null) {
            error.put("data", data);
        }
        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("jsonrpc", "2.0");
        resp.put("id", requestId);
        resp.put("error", error);
        return resp;
    }

    static Map<String, Object> makeNotification(String method, Map<String, Object> params) {
        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("jsonrpc", "2.0");
        resp.put("method", method);
        resp.put("params", params);
        return resp;
    }

    // --- I/O helpers ---

    private static Object getRequestId(Map<String, Object> msg) {
        return msg != null ? msg.get("id") : null;
    }

    private void writeLine(OutputStream out, Map<String, Object> msg) throws IOException {
        byte[] json = MAPPER.writeValueAsBytes(msg);
        out.write(json);
        out.write('\n');
        out.flush();
    }
}
