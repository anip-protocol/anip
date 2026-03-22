package dev.anip.service;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.module.paramnames.ParameterNamesModule;

import dev.anip.core.ANIPError;
import dev.anip.core.AuditEntry;
import dev.anip.core.AuditFilters;
import dev.anip.core.AuditResponse;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.Checkpoint;
import dev.anip.core.CheckpointDetailResponse;
import dev.anip.core.CheckpointListResponse;
import dev.anip.core.Constants;
import dev.anip.core.CostActual;
import dev.anip.core.DelegationToken;
import dev.anip.core.HealthReport;
import dev.anip.core.PermissionResponse;
import dev.anip.core.StorageHealth;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.crypto.JwksSerializer;
import dev.anip.crypto.JwsSigner;
import dev.anip.crypto.KeyManager;
import dev.anip.server.AuditLog;
import dev.anip.server.CheckpointManager;
import dev.anip.server.DelegationEngine;
import dev.anip.server.PostgresStorage;
import dev.anip.server.SqliteStorage;
import dev.anip.server.Storage;

import java.time.Duration;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Function;

/**
 * Main ANIP service runtime. Orchestrates crypto, server, and storage
 * into a usable ANIP runtime with background workers, hooks, and streaming.
 */
public class ANIPService {

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .registerModule(new ParameterNamesModule())
            .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
            .setSerializationInclusion(JsonInclude.Include.NON_NULL)
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
            .configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);

    private final String serviceId;
    private final String trustLevel;
    private final Map<String, CapabilityDef> capabilities;
    private final String storageDSN;
    private final String keyPath;
    private final Function<String, Optional<String>> authenticate;
    private final ObservabilityHooks hooks;
    private final CheckpointPolicy checkpointPolicy;
    private final int retentionIntervalSeconds;

    private Storage storage;
    private KeyManager keys;
    private Instant startedAt;
    private volatile boolean retentionRunning;

    private ScheduledExecutorService scheduler;
    private ScheduledFuture<?> retentionFuture;
    private ScheduledFuture<?> checkpointFuture;

    /**
     * Creates a new ANIPService from the given configuration.
     * Call {@link #start()} to initialize storage and keys before use.
     */
    public ANIPService(ServiceConfig config) {
        this.serviceId = config.getServiceId();

        String trust = config.getTrust();
        this.trustLevel = (trust != null && !trust.isEmpty()) ? trust : "signed";

        String dsn = config.getStorage();
        this.storageDSN = (dsn != null && !dsn.isEmpty()) ? dsn : ":memory:";

        this.keyPath = config.getKeyPath();
        this.authenticate = config.getAuthenticate();
        this.hooks = config.getHooks();
        this.checkpointPolicy = config.getCheckpointPolicy();

        int retInterval = config.getRetentionIntervalSeconds();
        if (retInterval == 0) {
            retInterval = 60;
        }
        if (retInterval < 0) {
            retInterval = 0; // disabled
        }
        this.retentionIntervalSeconds = retInterval;

        this.capabilities = new LinkedHashMap<>();
        if (config.getCapabilities() != null) {
            for (CapabilityDef cap : config.getCapabilities()) {
                this.capabilities.put(cap.getDeclaration().getName(), cap);
            }
        }
    }

    /**
     * Initializes storage, loads or generates keys, and starts background workers.
     */
    public void start() throws Exception {
        // Parse storage DSN.
        if (storageDSN.equals(":memory:") || storageDSN.isEmpty()) {
            storage = new SqliteStorage(":memory:");
        } else if (storageDSN.startsWith("sqlite:///")) {
            String dbPath = storageDSN.substring("sqlite:///".length());
            storage = new SqliteStorage(dbPath);
        } else if (storageDSN.startsWith("postgres://") || storageDSN.startsWith("postgresql://")) {
            storage = new PostgresStorage(storageDSN);
        } else {
            throw new IllegalArgumentException("Unsupported storage: " + storageDSN);
        }

        // Initialize keys.
        keys = KeyManager.create(keyPath);
        startedAt = Instant.now();

        // Start background workers.
        int workerCount = 0;
        if (retentionIntervalSeconds > 0) workerCount++;
        if (checkpointPolicy != null) workerCount++;

        if (workerCount > 0) {
            scheduler = Executors.newScheduledThreadPool(workerCount);

            if (retentionIntervalSeconds > 0) {
                retentionRunning = true;
                String holderId = "retention-" + serviceId + "-" + System.nanoTime();
                retentionFuture = scheduler.scheduleAtFixedRate(
                        () -> runRetention(holderId),
                        retentionIntervalSeconds, retentionIntervalSeconds, TimeUnit.SECONDS
                );
            }

            if (checkpointPolicy != null) {
                int interval = checkpointPolicy.getIntervalSeconds();
                if (interval <= 0) interval = 60;
                int minEntries = checkpointPolicy.getMinEntries();
                if (minEntries <= 0) minEntries = 1;
                String holderId = "checkpoint-" + serviceId + "-" + System.nanoTime();
                int finalInterval = interval;
                int finalMinEntries = minEntries;
                checkpointFuture = scheduler.scheduleAtFixedRate(
                        () -> runCheckpoint(holderId, finalInterval, finalMinEntries),
                        interval, interval, TimeUnit.SECONDS
                );
            }
        }
    }

    /**
     * Stops background workers and releases storage resources.
     * Safe to call multiple times.
     */
    public void shutdown() {
        if (scheduler != null) {
            if (retentionFuture != null) retentionFuture.cancel(false);
            if (checkpointFuture != null) checkpointFuture.cancel(false);
            scheduler.shutdown();
            try {
                if (!scheduler.awaitTermination(5, TimeUnit.SECONDS)) {
                    scheduler.shutdownNow();
                }
            } catch (InterruptedException e) {
                scheduler.shutdownNow();
                Thread.currentThread().interrupt();
            }
            scheduler = null;
        }
        retentionRunning = false;
        if (storage != null) {
            try {
                storage.close();
            } catch (Exception ignored) {
            }
        }
    }

    // --- Authentication ---

    /**
     * Tries bootstrap authentication only (API keys, external auth).
     * Returns the principal if authenticated, or empty otherwise.
     */
    public Optional<String> authenticateBearer(String bearer) {
        if (authenticate != null) {
            return authenticate.apply(bearer);
        }
        return Optional.empty();
    }

    /**
     * Verifies a JWT and returns the stored DelegationToken.
     */
    public DelegationToken resolveBearerToken(String jwt) throws Exception {
        DelegationToken token;
        try {
            token = DelegationEngine.resolveBearerToken(keys, storage, serviceId, jwt);
        } catch (ANIPError e) {
            fireAuthFailure(e.getErrorType(), e.getDetail());
            throw e;
        } catch (Exception e) {
            fireAuthFailure(Constants.FAILURE_INVALID_TOKEN, e.getMessage());
            throw e;
        }
        fireTokenResolved(token.getTokenId(), token.getSubject());
        return token;
    }

    /**
     * Issues a delegation token for the authenticated principal.
     */
    public TokenResponse issueToken(String principal, TokenRequest req) throws Exception {
        TokenResponse resp = DelegationEngine.issueDelegationToken(keys, storage, serviceId, principal, req);
        fireTokenIssued(resp.getTokenId(), principal, req.getCapability());
        return resp;
    }

    // --- Invocation ---

    /**
     * Unary invocation with full hook coverage.
     */
    public Map<String, Object> invoke(String capName, DelegationToken token,
                                       Map<String, Object> params, InvokeOpts opts) {
        String invocationId = Constants.generateInvocationId();
        long invokeStart = System.currentTimeMillis();
        boolean invokeSuccess = false;

        try {
            // 1. Look up capability.
            CapabilityDef capDef = capabilities.get(capName);
            if (capDef == null) {
                Map<String, Object> resp = new LinkedHashMap<>();
                resp.put("success", false);
                resp.put("failure", Map.of(
                        "type", Constants.FAILURE_UNKNOWN_CAPABILITY,
                        "detail", "Capability '" + capName + "' not found"
                ));
                resp.put("invocation_id", invocationId);
                resp.put("client_reference_id", opts != null ? opts.getClientReferenceId() : null);
                return resp;
            }

            String clientRefId = opts != null ? opts.getClientReferenceId() : null;

            // Fire OnInvokeStart hook.
            fireInvokeStart(invocationId, capName, token.getSubject());

            // 2. Check streaming support.
            if (opts != null && opts.isStream()) {
                Map<String, Object> resp = new LinkedHashMap<>();
                resp.put("success", false);
                resp.put("failure", Map.of(
                        "type", Constants.FAILURE_STREAMING_NOT_SUPPORTED,
                        "detail", "Use invokeStream for streaming invocations"
                ));
                resp.put("invocation_id", invocationId);
                resp.put("client_reference_id", clientRefId);
                return resp;
            }

            // 3. Validate token scope covers capability's minimum_scope.
            try {
                DelegationEngine.validateScope(token, capDef.getDeclaration().getMinimumScope());
            } catch (ANIPError e) {
                fireScopeValidation(capName, false);
                Map<String, Object> failure = new LinkedHashMap<>();
                failure.put("type", e.getErrorType());
                failure.put("detail", e.getDetail());
                if (e.getResolution() != null) {
                    failure.put("resolution", Map.of("action", e.getResolution().getAction()));
                }

                appendAuditEntry(capName, token, false, e.getErrorType(), null, null,
                        invocationId, clientRefId);

                Map<String, Object> resp = new LinkedHashMap<>();
                resp.put("success", false);
                resp.put("failure", failure);
                resp.put("invocation_id", invocationId);
                resp.put("client_reference_id", clientRefId);
                return resp;
            }

            // Fire scope validation hook (granted).
            fireScopeValidation(capName, true);

            // 4. Build invocation context.
            String rootPrincipal = token.getRootPrincipal();
            if (rootPrincipal == null || rootPrincipal.isEmpty()) {
                rootPrincipal = token.getIssuer();
            }

            InvocationContext ctx = new InvocationContext(
                    token, rootPrincipal, token.getSubject(),
                    invocationId, clientRefId,
                    token.getScope(), List.of(token.getTokenId()),
                    payload -> true // no-op for unary
            );

            // 5. Call handler.
            Map<String, Object> result;
            try {
                result = capDef.getHandler().apply(ctx, params);
            } catch (ANIPError e) {
                appendAuditEntry(capName, token, false, e.getErrorType(),
                        Map.of("detail", e.getDetail()), null, invocationId, clientRefId);
                Map<String, Object> resp = new LinkedHashMap<>();
                resp.put("success", false);
                resp.put("failure", Map.of("type", e.getErrorType(), "detail", e.getDetail()));
                resp.put("invocation_id", invocationId);
                resp.put("client_reference_id", clientRefId);
                return resp;
            } catch (Exception e) {
                appendAuditEntry(capName, token, false, Constants.FAILURE_INTERNAL_ERROR,
                        null, null, invocationId, clientRefId);
                Map<String, Object> resp = new LinkedHashMap<>();
                resp.put("success", false);
                resp.put("failure", Map.of("type", Constants.FAILURE_INTERNAL_ERROR, "detail", "Internal error"));
                resp.put("invocation_id", invocationId);
                resp.put("client_reference_id", clientRefId);
                return resp;
            }

            // 6. Extract cost actual from context.
            CostActual costActual = ctx.getCostActual();

            // 7. Log audit (success).
            appendAuditEntry(capName, token, true, "", result, costActual, invocationId, clientRefId);

            // 8. Build response.
            Map<String, Object> resp = new LinkedHashMap<>();
            resp.put("success", true);
            resp.put("result", result);
            resp.put("invocation_id", invocationId);
            resp.put("client_reference_id", clientRefId);
            if (costActual != null) {
                resp.put("cost_actual", costActual);
            }

            invokeSuccess = true;
            return resp;
        } finally {
            long durationMs = System.currentTimeMillis() - invokeStart;
            fireInvokeComplete(invocationId, capName, invokeSuccess, durationMs);
            fireInvokeDuration(capName, durationMs, invokeSuccess);
        }
    }

    /**
     * Streaming invocation with BlockingQueue.
     * Handler runs in a separate thread. EmitProgress pushes to BlockingQueue.
     * Terminal event: exactly one completed/failed. Cancel sets a flag so emitProgress returns false.
     */
    public StreamResult invokeStream(String capName, DelegationToken token,
                                      Map<String, Object> params, InvokeOpts opts) throws ANIPError {
        String invocationId = Constants.generateInvocationId();

        // 1. Look up capability.
        CapabilityDef capDef = capabilities.get(capName);
        if (capDef == null) {
            throw new ANIPError(Constants.FAILURE_UNKNOWN_CAPABILITY,
                    "Capability '" + capName + "' not found");
        }

        // 2. Check streaming support.
        if (!capabilitySupportsStreaming(capDef.getDeclaration())) {
            throw new ANIPError(Constants.FAILURE_STREAMING_NOT_SUPPORTED,
                    "Capability '" + capName + "' does not support streaming");
        }

        // 3. Validate token scope.
        DelegationEngine.validateScope(token, capDef.getDeclaration().getMinimumScope());

        // 4. Build invocation context with streaming EmitProgress.
        String rootPrincipal = token.getRootPrincipal();
        if (rootPrincipal == null || rootPrincipal.isEmpty()) {
            rootPrincipal = token.getIssuer();
        }

        String clientRefId = opts != null ? opts.getClientReferenceId() : null;

        BlockingQueue<StreamEvent> queue = new LinkedBlockingQueue<>(16);
        AtomicBoolean closed = new AtomicBoolean(false);

        Function<Map<String, Object>, Boolean> emitProgress = payload -> {
            if (closed.get()) {
                return false;
            }
            Map<String, Object> eventPayload = new LinkedHashMap<>();
            eventPayload.put("invocation_id", invocationId);
            eventPayload.put("client_reference_id", clientRefId);
            eventPayload.put("timestamp", DateTimeFormatter.ISO_INSTANT.format(Instant.now()));
            eventPayload.put("payload", payload);
            try {
                queue.put(new StreamEvent("progress", eventPayload));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
            return !closed.get();
        };

        InvocationContext ctx = new InvocationContext(
                token, rootPrincipal, token.getSubject(),
                invocationId, clientRefId,
                token.getScope(), List.of(token.getTokenId()),
                emitProgress
        );

        // 5. Run handler in separate thread.
        Thread handlerThread = new Thread(() -> {
            long invokeStart = System.currentTimeMillis();
            boolean success = false;
            try {
                Map<String, Object> result = capDef.getHandler().apply(ctx, params);

                // Success -- send completed event.
                CostActual costActual = ctx.getCostActual();
                appendAuditEntry(capName, token, true, "", result, costActual,
                        invocationId, clientRefId);

                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("invocation_id", invocationId);
                payload.put("client_reference_id", clientRefId);
                payload.put("timestamp", DateTimeFormatter.ISO_INSTANT.format(Instant.now()));
                payload.put("success", true);
                payload.put("result", result);
                payload.put("cost_actual", costActual);

                queue.put(new StreamEvent("completed", payload));
                success = true;
            } catch (ANIPError e) {
                appendAuditEntry(capName, token, false, e.getErrorType(),
                        Map.of("detail", e.getDetail()), null, invocationId, clientRefId);

                Map<String, Object> failureObj = new LinkedHashMap<>();
                failureObj.put("type", e.getErrorType());
                failureObj.put("detail", e.getDetail());
                failureObj.put("retry", e.isRetry());
                failureObj.put("resolution", e.getResolution() != null
                        ? Map.of("action", e.getResolution().getAction()) : null);

                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("invocation_id", invocationId);
                payload.put("client_reference_id", clientRefId);
                payload.put("timestamp", DateTimeFormatter.ISO_INSTANT.format(Instant.now()));
                payload.put("success", false);
                payload.put("failure", failureObj);

                try {
                    queue.put(new StreamEvent("failed", payload));
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                }
            } catch (Exception e) {
                appendAuditEntry(capName, token, false, Constants.FAILURE_INTERNAL_ERROR,
                        null, null, invocationId, clientRefId);

                Map<String, Object> failureObj = new LinkedHashMap<>();
                failureObj.put("type", Constants.FAILURE_INTERNAL_ERROR);
                failureObj.put("detail", "Internal error");
                failureObj.put("resolution", null);
                failureObj.put("retry", false);

                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("invocation_id", invocationId);
                payload.put("client_reference_id", clientRefId);
                payload.put("timestamp", DateTimeFormatter.ISO_INSTANT.format(Instant.now()));
                payload.put("success", false);
                payload.put("failure", failureObj);

                try {
                    queue.put(new StreamEvent("failed", payload));
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                }
            } finally {
                closed.set(true);
                // Send poison pill to signal end of stream.
                try {
                    queue.put(new StreamEvent(StreamResult.DONE_TYPE, Map.of()));
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                }
                long durationMs = System.currentTimeMillis() - invokeStart;
                fireInvokeComplete(invocationId, capName, success, durationMs);
                fireInvokeDuration(capName, durationMs, success);
            }
        }, "anip-stream-" + invocationId);
        handlerThread.setDaemon(true);
        handlerThread.start();

        Runnable cancel = () -> closed.set(true);
        return new StreamResult(queue, cancel);
    }

    // --- Permissions ---

    /**
     * Checks the token's scope against all registered capabilities
     * and returns what the token can and cannot do.
     */
    public PermissionResponse discoverPermissions(DelegationToken token) {
        List<PermissionResponse.AvailableCapability> available = new ArrayList<>();
        List<PermissionResponse.RestrictedCapability> restricted = new ArrayList<>();
        List<PermissionResponse.DeniedCapability> denied = new ArrayList<>();

        // Build token scope bases.
        List<String> tokenScopes = token.getScope() != null ? token.getScope() : List.of();
        record ScopeEntry(String base, String full) {}
        List<ScopeEntry> tokenScopeEntries = tokenScopes.stream()
                .map(s -> new ScopeEntry(s.split(":")[0], s))
                .toList();

        String rootPrincipal = token.getRootPrincipal();
        if (rootPrincipal == null || rootPrincipal.isEmpty()) {
            rootPrincipal = token.getIssuer();
        }

        for (var entry : capabilities.entrySet()) {
            String name = entry.getKey();
            CapabilityDef cap = entry.getValue();
            List<String> requiredScopes = cap.getDeclaration().getMinimumScope();
            if (requiredScopes == null) requiredScopes = List.of();

            List<String> matchedScopeStrs = new ArrayList<>();
            List<String> missing = new ArrayList<>();

            for (String required : requiredScopes) {
                String matchedFull = null;
                for (ScopeEntry se : tokenScopeEntries) {
                    if (se.base().equals(required) || required.startsWith(se.base() + ".")) {
                        matchedFull = se.full();
                        break;
                    }
                }
                if (matchedFull != null) {
                    matchedScopeStrs.add(matchedFull);
                } else {
                    missing.add(required);
                }
            }

            if (missing.isEmpty()) {
                Map<String, Object> constraints = new HashMap<>();
                for (String scopeStr : matchedScopeStrs) {
                    if (scopeStr.contains(":max_$")) {
                        String[] parts = scopeStr.split(":max_\\$", 2);
                        if (parts.length == 2) {
                            try {
                                double maxBudget = Double.parseDouble(parts[1]);
                                constraints.put("budget_remaining", maxBudget);
                                constraints.put("currency", "USD");
                            } catch (NumberFormatException ignored) {
                            }
                        }
                    }
                }
                available.add(new PermissionResponse.AvailableCapability(
                        name, String.join(", ", matchedScopeStrs), constraints
                ));
            } else {
                boolean hasAdmin = missing.stream().anyMatch(s -> s.startsWith("admin."));
                if (hasAdmin) {
                    denied.add(new PermissionResponse.DeniedCapability(
                            name, "requires admin principal"
                    ));
                } else {
                    restricted.add(new PermissionResponse.RestrictedCapability(
                            name,
                            "delegation chain lacks scope(s): " + String.join(", ", missing),
                            rootPrincipal
                    ));
                }
            }
        }

        return new PermissionResponse(available, restricted, denied);
    }

    // --- Discovery ---

    /**
     * Builds the full discovery document per SPEC.md section 6.1.
     */
    public Map<String, Object> getDiscovery(String baseUrl) {
        Map<String, Object> capsSummary = new LinkedHashMap<>();
        for (var entry : capabilities.entrySet()) {
            String name = entry.getKey();
            CapabilityDeclaration decl = entry.getValue().getDeclaration();
            String sideEffectType = "";
            if (decl.getSideEffect() != null && decl.getSideEffect().getType() != null) {
                sideEffectType = decl.getSideEffect().getType();
            }
            boolean financial = decl.getCost() != null && decl.getCost().getFinancial() != null;

            Map<String, Object> capInfo = new LinkedHashMap<>();
            capInfo.put("description", decl.getDescription());
            capInfo.put("side_effect", sideEffectType);
            capInfo.put("minimum_scope", decl.getMinimumScope());
            capInfo.put("financial", financial);
            capInfo.put("contract", decl.getContractVersion());
            capsSummary.put(name, capInfo);
        }

        Map<String, Object> doc = new LinkedHashMap<>();
        doc.put("protocol", Constants.PROTOCOL_VERSION);
        doc.put("compliance", "anip-compliant");
        doc.put("profile", Constants.DEFAULT_PROFILE);
        doc.put("auth", Map.of(
                "delegation_token_required", true,
                "supported_formats", List.of("anip-v1"),
                "minimum_scope_for_discovery", "none"
        ));
        doc.put("capabilities", capsSummary);
        doc.put("trust_level", trustLevel);
        doc.put("posture", Map.of(
                "audit", Map.of(
                        "retention", "P90D",
                        "retention_enforced", retentionRunning
                ),
                "failure_disclosure", Map.of("detail_level", "full"),
                "anchoring", Map.of("enabled", false, "proofs_available", false)
        ));
        doc.put("endpoints", Map.of(
                "manifest", "/anip/manifest",
                "permissions", "/anip/permissions",
                "invoke", "/anip/invoke/{capability}",
                "tokens", "/anip/tokens",
                "audit", "/anip/audit",
                "checkpoints", "/anip/checkpoints",
                "jwks", "/.well-known/jwks.json"
        ));

        if (baseUrl != null && !baseUrl.isEmpty()) {
            doc.put("base_url", baseUrl);
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("anip_discovery", doc);
        return result;
    }

    /**
     * Returns the full capability manifest as a map.
     */
    @SuppressWarnings("unchecked")
    public Object getManifest() {
        Map<String, Object> capsMap = new LinkedHashMap<>();
        for (var entry : capabilities.entrySet()) {
            try {
                String json = MAPPER.writeValueAsString(entry.getValue().getDeclaration());
                capsMap.put(entry.getKey(), MAPPER.readValue(json, Map.class));
            } catch (JsonProcessingException e) {
                throw new RuntimeException("Failed to serialize capability", e);
            }
        }

        Map<String, Object> manifest = new LinkedHashMap<>();
        manifest.put("protocol", Constants.PROTOCOL_VERSION);
        manifest.put("profile", Constants.DEFAULT_PROFILE);
        manifest.put("capabilities", capsMap);
        manifest.put("trust", Map.of("level", trustLevel));
        manifest.put("service_identity", Map.of(
                "id", serviceId,
                "jwks_uri", "/.well-known/jwks.json",
                "issuer_mode", "first-party"
        ));

        return manifest;
    }

    /**
     * Returns the manifest as canonical JSON bytes and its detached JWS signature.
     */
    @SuppressWarnings("unchecked")
    public SignedManifest getSignedManifest() {
        Object manifest = getManifest();

        byte[] bodyBytes;
        try {
            bodyBytes = MAPPER.writeValueAsBytes(manifest);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to serialize manifest", e);
        }

        String signature = "";
        try {
            signature = JwsSigner.signDetachedJws(keys, bodyBytes);
        } catch (Exception ignored) {
        }

        return new SignedManifest(bodyBytes, signature);
    }

    /**
     * Returns the JWKS document for this service.
     */
    public Map<String, Object> getJwks() {
        return JwksSerializer.toJwks(keys);
    }

    /**
     * Returns a single capability declaration by name, or null if not found.
     */
    public CapabilityDeclaration getCapabilityDeclaration(String name) {
        CapabilityDef cap = capabilities.get(name);
        return cap != null ? cap.getDeclaration() : null;
    }

    // --- Audit ---

    /**
     * Queries audit entries scoped to the token's root principal.
     */
    public AuditResponse queryAudit(DelegationToken token, AuditFilters filters) throws Exception {
        String rootPrincipal = token.getRootPrincipal();
        if (rootPrincipal == null || rootPrincipal.isEmpty()) {
            rootPrincipal = token.getIssuer();
        }
        return AuditLog.queryAudit(storage, rootPrincipal, filters);
    }

    // --- Checkpoints ---

    /**
     * Returns a list of checkpoints.
     */
    public CheckpointListResponse listCheckpoints(int limit) throws Exception {
        if (limit <= 0) limit = 50;
        List<Checkpoint> checkpoints = storage.listCheckpoints(limit);
        if (checkpoints == null) checkpoints = List.of();
        return new CheckpointListResponse(checkpoints, null);
    }

    /**
     * Returns a single checkpoint with optional inclusion proof.
     */
    public CheckpointDetailResponse getCheckpoint(String id, boolean includeProof,
                                                    int leafIndex) throws Exception {
        Checkpoint cp = storage.getCheckpointById(id);
        if (cp == null) {
            throw new ANIPError(Constants.FAILURE_NOT_FOUND,
                    "checkpoint '" + id + "' not found");
        }

        // Convert checkpoint to map.
        @SuppressWarnings("unchecked")
        Map<String, Object> cpMap = MAPPER.convertValue(cp, Map.class);

        Map<String, Object> inclusionProof = null;
        String proofUnavailable = null;

        if (includeProof) {
            CheckpointManager.InclusionProofResult proofResult =
                    CheckpointManager.generateInclusionProof(storage, cp, leafIndex);
            if (proofResult.proofUnavailable() != null) {
                proofUnavailable = proofResult.proofUnavailable();
            } else {
                inclusionProof = new LinkedHashMap<>();
                inclusionProof.put("leaf_index", leafIndex);
                inclusionProof.put("merkle_root", cp.getMerkleRoot());
                inclusionProof.put("path", proofResult.proofSteps());
            }
        }

        return new CheckpointDetailResponse(cpMap, inclusionProof, proofUnavailable);
    }

    /**
     * Creates a new checkpoint from audit entries.
     */
    public Checkpoint createCheckpoint() throws Exception {
        return CheckpointManager.createCheckpoint(keys, storage, serviceId);
    }

    // --- Health ---

    /**
     * Returns the current health status of the service.
     */
    public HealthReport getHealth() {
        String storageType = "sqlite";
        if (storageDSN.startsWith("postgres://") || storageDSN.startsWith("postgresql://")) {
            storageType = "postgres";
        }

        boolean connected = storage != null;
        String status = connected ? "healthy" : "unhealthy";

        String uptime = "0s";
        if (startedAt != null) {
            Duration d = Duration.between(startedAt, Instant.now());
            uptime = formatDuration(d);
        }

        return new HealthReport(status, new StorageHealth(connected, storageType),
                uptime, Constants.PROTOCOL_VERSION);
    }

    /**
     * Returns the service identifier.
     */
    public String getServiceId() {
        return serviceId;
    }

    // --- Internal methods ---

    private boolean capabilitySupportsStreaming(CapabilityDeclaration decl) {
        if (decl.getResponseModes() == null) return false;
        return decl.getResponseModes().contains("streaming");
    }

    private void appendAuditEntry(String capability, DelegationToken token,
                                   boolean success, String failureType,
                                   Map<String, Object> resultSummary, CostActual costActual,
                                   String invocationId, String clientReferenceId) {
        String rootPrincipal = token.getRootPrincipal();
        if (rootPrincipal == null || rootPrincipal.isEmpty()) {
            rootPrincipal = token.getIssuer();
        }

        AuditEntry entry = new AuditEntry();
        entry.setCapability(capability);
        entry.setTokenId(token.getTokenId());
        entry.setIssuer(token.getIssuer());
        entry.setSubject(token.getSubject());
        entry.setRootPrincipal(rootPrincipal);
        entry.setSuccess(success);
        entry.setFailureType(failureType);
        entry.setResultSummary(resultSummary);
        entry.setCostActual(costActual);
        entry.setDelegationChain(List.of(token.getTokenId()));
        entry.setInvocationId(invocationId);
        entry.setClientReferenceId(clientReferenceId);

        try {
            AuditLog.appendAudit(keys, storage, entry);
            fireAuditAppend(entry.getSequenceNumber(), capability, invocationId);
        } catch (Exception ignored) {
            // Best effort -- don't fail invocation if audit logging fails.
        }
    }

    // --- Hook helpers (null-safe, exception-safe) ---

    private void callHook(Runnable fn) {
        if (fn == null) return;
        try {
            fn.run();
        } catch (Exception ignored) {
        }
    }

    private void fireTokenIssued(String tokenId, String subject, String capability) {
        if (hooks != null && hooks.getOnTokenIssued() != null) {
            callHook(() -> hooks.getOnTokenIssued().accept(tokenId, subject, capability));
        }
    }

    private void fireTokenResolved(String tokenId, String subject) {
        if (hooks != null && hooks.getOnTokenResolved() != null) {
            callHook(() -> hooks.getOnTokenResolved().accept(tokenId, subject));
        }
    }

    private void fireInvokeStart(String invocationId, String capability, String subject) {
        if (hooks != null && hooks.getOnInvokeStart() != null) {
            callHook(() -> hooks.getOnInvokeStart().accept(invocationId, capability, subject));
        }
    }

    private void fireInvokeComplete(String invocationId, String capability,
                                     boolean success, long durationMs) {
        if (hooks != null && hooks.getOnInvokeComplete() != null) {
            callHook(() -> hooks.getOnInvokeComplete().accept(invocationId, capability, success, durationMs));
        }
    }

    private void fireAuditAppend(int seqNum, String capability, String invocationId) {
        if (hooks != null && hooks.getOnAuditAppend() != null) {
            callHook(() -> hooks.getOnAuditAppend().accept(seqNum, capability, invocationId));
        }
    }

    private void fireAuthFailure(String failureType, String detail) {
        if (hooks != null && hooks.getOnAuthFailure() != null) {
            callHook(() -> hooks.getOnAuthFailure().accept(failureType, detail));
        }
    }

    private void fireScopeValidation(String capability, boolean granted) {
        if (hooks != null && hooks.getOnScopeValidation() != null) {
            callHook(() -> hooks.getOnScopeValidation().accept(capability, granted));
        }
    }

    private void fireInvokeDuration(String capability, long durationMs, boolean success) {
        if (hooks != null && hooks.getOnInvokeDuration() != null) {
            callHook(() -> hooks.getOnInvokeDuration().accept(capability, durationMs, success));
        }
    }

    // --- Background workers ---

    private void runRetention(String holderId) {
        try {
            boolean acquired = storage.tryAcquireLeader("retention", holderId,
                    retentionIntervalSeconds * 2);
            if (!acquired) return;
            String now = DateTimeFormatter.ISO_INSTANT.format(Instant.now());
            storage.deleteExpiredAuditEntries(now);
        } catch (Exception ignored) {
        }
    }

    private void runCheckpoint(String holderId, int interval, int minEntries) {
        try {
            boolean acquired = storage.tryAcquireLeader("checkpoint", holderId, interval * 2);
            if (!acquired) return;

            int maxSeq = storage.getMaxAuditSequence();
            if (maxSeq == 0) return;

            List<Checkpoint> checkpoints = storage.listCheckpoints(100);
            int lastCovered = 0;
            if (checkpoints != null && !checkpoints.isEmpty()) {
                Checkpoint last = checkpoints.get(checkpoints.size() - 1);
                Integer ls = last.getRange().get("last_sequence");
                if (ls != null) lastCovered = ls;
            }

            int newEntries = maxSeq - lastCovered;
            if (newEntries < minEntries) return;

            Checkpoint cp = createCheckpoint();
            if (cp != null && hooks != null && hooks.getOnCheckpointCreated() != null) {
                callHook(() -> hooks.getOnCheckpointCreated().accept(
                        cp.getCheckpointId(), cp.getEntryCount()));
            }
        } catch (Exception ignored) {
        }
    }

    private static String formatDuration(Duration d) {
        long totalSeconds = d.getSeconds();
        if (totalSeconds < 60) {
            return totalSeconds + "s";
        }
        long minutes = totalSeconds / 60;
        long seconds = totalSeconds % 60;
        if (minutes < 60) {
            return minutes + "m" + seconds + "s";
        }
        long hours = minutes / 60;
        minutes = minutes % 60;
        return hours + "h" + minutes + "m" + seconds + "s";
    }
}
