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
import dev.anip.core.BindingRequirement;
import dev.anip.core.Budget;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.ControlRequirement;
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
    private RetentionPolicy retentionPolicy;
    private String disclosureLevel;
    private Map<String, String> disclosurePolicy;
    private AuditAggregator aggregator;

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

        this.retentionPolicy = config.getRetentionPolicy() != null
            ? config.getRetentionPolicy() : new RetentionPolicy(null, null);
        this.disclosureLevel = config.getDisclosureLevel() != null
            ? config.getDisclosureLevel() : "full";
        this.disclosurePolicy = config.getDisclosurePolicy();
        if (config.getAggregationWindowSeconds() > 0) {
            this.aggregator = new AuditAggregator(config.getAggregationWindowSeconds());
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
        if (aggregator != null) workerCount++;

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

            if (aggregator != null) {
                scheduler.scheduleAtFixedRate(this::flushAggregator, 10, 10, TimeUnit.SECONDS);
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

        String requestTaskId = opts != null ? opts.getTaskId() : null;
        String parentInvocationId = opts != null ? opts.getParentInvocationId() : null;

        try {
            // task_id precedence: token purpose.task_id is authoritative
            String tokenTaskId = (token.getPurpose() != null) ? token.getPurpose().getTaskId() : null;
            if (tokenTaskId != null && !tokenTaskId.isEmpty()
                    && requestTaskId != null && !requestTaskId.isEmpty()
                    && !requestTaskId.equals(tokenTaskId)) {
                Map<String, Object> resp = new LinkedHashMap<>();
                resp.put("success", false);
                resp.put("failure", Map.of(
                        "type", Constants.FAILURE_PURPOSE_MISMATCH,
                        "detail", "Request task_id '" + requestTaskId
                                + "' does not match token purpose task_id '" + tokenTaskId + "'",
                        "resolution", Map.of("action", "use_token_task_id", "requires", "matching task_id or omit from request"),
                        "retry", false
                ));
                resp.put("invocation_id", invocationId);
                resp.put("client_reference_id", opts != null ? opts.getClientReferenceId() : null);
                resp.put("task_id", requestTaskId);
                resp.put("parent_invocation_id", parentInvocationId);
                return resp;
            }
            String effectiveTaskId = (requestTaskId != null && !requestTaskId.isEmpty())
                    ? requestTaskId : tokenTaskId;

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
                resp.put("task_id", effectiveTaskId);
                resp.put("parent_invocation_id", parentInvocationId);
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
                resp.put("task_id", effectiveTaskId);
                resp.put("parent_invocation_id", parentInvocationId);
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

                String sideEffectType = capDef.getDeclaration().getSideEffect() != null
                    ? capDef.getDeclaration().getSideEffect().getType() : null;
                appendAuditEntry(capName, token, false, e.getErrorType(), null, null,
                        invocationId, clientRefId, effectiveTaskId, parentInvocationId,
                        sideEffectType);

                Map<String, Object> tokenClaims = tokenClaimsMap(token);
                String effectiveLevel = DisclosureControl.resolve(disclosureLevel, tokenClaims, disclosurePolicy);
                failure = FailureRedaction.redact(failure, effectiveLevel);

                Map<String, Object> resp = new LinkedHashMap<>();
                resp.put("success", false);
                resp.put("failure", failure);
                resp.put("invocation_id", invocationId);
                resp.put("client_reference_id", clientRefId);
                resp.put("task_id", effectiveTaskId);
                resp.put("parent_invocation_id", parentInvocationId);
                return resp;
            }

            // Fire scope validation hook (granted).
            fireScopeValidation(capName, true);

            // --- Budget, binding, and control requirement enforcement (v0.13) ---

            // Parse invocation-level budget hint.
            Budget requestBudget = opts != null ? opts.getBudget() : null;

            // Determine effective budget (token is ceiling, invocation hint can only narrow).
            Budget effectiveBudget = null;
            if (token.getConstraints() != null && token.getConstraints().getBudget() != null) {
                effectiveBudget = token.getConstraints().getBudget();
                if (requestBudget != null) {
                    if (!requestBudget.getCurrency().equals(effectiveBudget.getCurrency())) {
                        Map<String, Object> failure = new LinkedHashMap<>();
                        failure.put("type", Constants.FAILURE_BUDGET_CURRENCY_MISMATCH);
                        failure.put("detail", "Invocation budget is in " + requestBudget.getCurrency()
                                + " but token budget is in " + effectiveBudget.getCurrency());
                        Map<String, Object> tokenClaims = tokenClaimsMap(token);
                        String effectiveLevel = DisclosureControl.resolve(disclosureLevel, tokenClaims, disclosurePolicy);
                        failure = FailureRedaction.redact(failure, effectiveLevel);
                        Map<String, Object> resp = new LinkedHashMap<>();
                        resp.put("success", false);
                        resp.put("failure", failure);
                        resp.put("invocation_id", invocationId);
                        resp.put("client_reference_id", clientRefId);
                        resp.put("task_id", effectiveTaskId);
                        resp.put("parent_invocation_id", parentInvocationId);
                        return resp;
                    }
                    double narrowedAmount = Math.min(effectiveBudget.getMaxAmount(), requestBudget.getMaxAmount());
                    effectiveBudget = new Budget(effectiveBudget.getCurrency(), narrowedAmount);
                }
            } else if (requestBudget != null) {
                effectiveBudget = requestBudget;
            }

            // Budget enforcement against declared cost.
            Double checkAmount = null;
            if (effectiveBudget != null) {
                CapabilityDeclaration decl = capDef.getDeclaration();
                if (decl.getCost() != null && decl.getCost().getFinancial() != null) {
                    if (!decl.getCost().getFinancial().getCurrency().equals(effectiveBudget.getCurrency())) {
                        Map<String, Object> failure = new LinkedHashMap<>();
                        failure.put("type", Constants.FAILURE_BUDGET_CURRENCY_MISMATCH);
                        failure.put("detail", "Token budget is in " + effectiveBudget.getCurrency()
                                + " but capability cost is in " + decl.getCost().getFinancial().getCurrency());
                        Map<String, Object> tokenClaims = tokenClaimsMap(token);
                        String effectiveLevel = DisclosureControl.resolve(disclosureLevel, tokenClaims, disclosurePolicy);
                        failure = FailureRedaction.redact(failure, effectiveLevel);
                        Map<String, Object> resp = new LinkedHashMap<>();
                        resp.put("success", false);
                        resp.put("failure", failure);
                        resp.put("invocation_id", invocationId);
                        resp.put("client_reference_id", clientRefId);
                        resp.put("task_id", effectiveTaskId);
                        resp.put("parent_invocation_id", parentInvocationId);
                        return resp;
                    }

                    String certainty = decl.getCost().getCertainty();
                    if (certainty != null) {
                        switch (certainty) {
                            case "fixed" -> checkAmount = decl.getCost().getFinancial().getAmount();
                            case "estimated" -> {
                                if (decl.getRequiresBinding() != null && !decl.getRequiresBinding().isEmpty()) {
                                    checkAmount = resolveBoundPrice(decl.getRequiresBinding(), params);
                                } else {
                                    Map<String, Object> failure = new LinkedHashMap<>();
                                    failure.put("type", Constants.FAILURE_BUDGET_NOT_ENFORCEABLE);
                                    failure.put("detail", "Capability " + capName
                                            + " has estimated cost but no requires_binding — budget cannot be enforced");
                                    Map<String, Object> tokenClaims = tokenClaimsMap(token);
                                    String effectiveLevel = DisclosureControl.resolve(disclosureLevel, tokenClaims, disclosurePolicy);
                                    failure = FailureRedaction.redact(failure, effectiveLevel);
                                    Map<String, Object> resp = new LinkedHashMap<>();
                                    resp.put("success", false);
                                    resp.put("failure", failure);
                                    resp.put("invocation_id", invocationId);
                                    resp.put("client_reference_id", clientRefId);
                                    resp.put("task_id", effectiveTaskId);
                                    resp.put("parent_invocation_id", parentInvocationId);
                                    return resp;
                                }
                            }
                            case "dynamic" -> checkAmount = decl.getCost().getFinancial().getUpperBound();
                        }
                    }

                    if (checkAmount != null && checkAmount > effectiveBudget.getMaxAmount()) {
                        Map<String, Object> failure = new LinkedHashMap<>();
                        failure.put("type", Constants.FAILURE_BUDGET_EXCEEDED);
                        failure.put("detail", "Cost $" + checkAmount + " exceeds budget $" + effectiveBudget.getMaxAmount());
                        Map<String, Object> tokenClaims = tokenClaimsMap(token);
                        String effectiveLevel = DisclosureControl.resolve(disclosureLevel, tokenClaims, disclosurePolicy);
                        failure = FailureRedaction.redact(failure, effectiveLevel);
                        Map<String, Object> resp = new LinkedHashMap<>();
                        resp.put("success", false);
                        resp.put("failure", failure);
                        resp.put("invocation_id", invocationId);
                        resp.put("client_reference_id", clientRefId);
                        resp.put("task_id", effectiveTaskId);
                        resp.put("parent_invocation_id", parentInvocationId);
                        Map<String, Object> budgetCtx = new LinkedHashMap<>();
                        budgetCtx.put("budget_max", effectiveBudget.getMaxAmount());
                        budgetCtx.put("budget_currency", effectiveBudget.getCurrency());
                        budgetCtx.put("cost_check_amount", checkAmount);
                        budgetCtx.put("cost_certainty", certainty);
                        resp.put("budget_context", budgetCtx);
                        return resp;
                    }
                }
            }

            // Binding enforcement.
            if (capDef.getDeclaration().getRequiresBinding() != null) {
                for (BindingRequirement binding : capDef.getDeclaration().getRequiresBinding()) {
                    Object val = params.get(binding.getField());
                    if (val == null) {
                        String sourceDesc = binding.getSourceCapability();
                        if (sourceDesc == null || sourceDesc.isEmpty()) {
                            sourceDesc = "source capability";
                        }
                        Map<String, Object> failure = new LinkedHashMap<>();
                        failure.put("type", Constants.FAILURE_BINDING_MISSING);
                        failure.put("detail", "Capability " + capName + " requires '" + binding.getField()
                                + "' (type: " + binding.getType() + ")");
                        failure.put("resolution", Map.of(
                                "action", "obtain_binding",
                                "requires", "invoke " + sourceDesc + " to obtain a " + binding.getField()
                        ));
                        Map<String, Object> tokenClaims = tokenClaimsMap(token);
                        String effectiveLevel = DisclosureControl.resolve(disclosureLevel, tokenClaims, disclosurePolicy);
                        failure = FailureRedaction.redact(failure, effectiveLevel);
                        Map<String, Object> resp = new LinkedHashMap<>();
                        resp.put("success", false);
                        resp.put("failure", failure);
                        resp.put("invocation_id", invocationId);
                        resp.put("client_reference_id", clientRefId);
                        resp.put("task_id", effectiveTaskId);
                        resp.put("parent_invocation_id", parentInvocationId);
                        return resp;
                    }
                    if (binding.getMaxAge() != null && !binding.getMaxAge().isEmpty()) {
                        long ageSeconds = resolveBindingAge(val);
                        if (ageSeconds >= 0) {
                            long maxAgeSeconds = parseISO8601DurationSeconds(binding.getMaxAge());
                            if (maxAgeSeconds > 0 && ageSeconds > maxAgeSeconds) {
                                String sourceDesc = binding.getSourceCapability();
                                if (sourceDesc == null || sourceDesc.isEmpty()) {
                                    sourceDesc = "source capability";
                                }
                                Map<String, Object> failure = new LinkedHashMap<>();
                                failure.put("type", Constants.FAILURE_BINDING_STALE);
                                failure.put("detail", "Binding '" + binding.getField()
                                        + "' has exceeded max_age of " + binding.getMaxAge());
                                failure.put("resolution", Map.of(
                                        "action", "refresh_binding",
                                        "requires", "invoke " + sourceDesc + " again for a fresh " + binding.getField()
                                ));
                                Map<String, Object> tokenClaims = tokenClaimsMap(token);
                                String effectiveLevel = DisclosureControl.resolve(disclosureLevel, tokenClaims, disclosurePolicy);
                                failure = FailureRedaction.redact(failure, effectiveLevel);
                                Map<String, Object> resp = new LinkedHashMap<>();
                                resp.put("success", false);
                                resp.put("failure", failure);
                                resp.put("invocation_id", invocationId);
                                resp.put("client_reference_id", clientRefId);
                                resp.put("task_id", effectiveTaskId);
                                resp.put("parent_invocation_id", parentInvocationId);
                                return resp;
                            }
                        }
                    }
                }
            }

            // Control requirement enforcement (reject only — no warn in v0.13).
            if (capDef.getDeclaration().getControlRequirements() != null) {
                for (ControlRequirement req : capDef.getDeclaration().getControlRequirements()) {
                    boolean satisfied = true;
                    switch (req.getType()) {
                        case "cost_ceiling" -> satisfied = effectiveBudget != null;
                        case "bound_reference" -> {
                            if (req.getField() != null && !req.getField().isEmpty()) {
                                Object val = params.get(req.getField());
                                satisfied = val != null;
                            } else {
                                satisfied = false;
                            }
                        }
                        case "freshness_window" -> {
                            if (req.getField() != null && !req.getField().isEmpty()) {
                                Object val = params.get(req.getField());
                                if (val != null) {
                                    long ageSeconds = resolveBindingAge(val);
                                    if (ageSeconds >= 0 && req.getMaxAge() != null && !req.getMaxAge().isEmpty()) {
                                        long maxAgeSeconds = parseISO8601DurationSeconds(req.getMaxAge());
                                        satisfied = maxAgeSeconds == 0 || ageSeconds <= maxAgeSeconds;
                                    }
                                } else {
                                    satisfied = false;
                                }
                            } else {
                                satisfied = false;
                            }
                        }
                        case "stronger_delegation_required" -> {
                            satisfied = token.getPurpose() != null
                                    && capName.equals(token.getPurpose().getCapability());
                        }
                    }

                    if (!satisfied) {
                        Map<String, Object> failure = new LinkedHashMap<>();
                        failure.put("type", Constants.FAILURE_CONTROL_REQUIREMENT_UNSATISFIED);
                        failure.put("detail", "Capability " + capName + " requires " + req.getType());
                        failure.put("unsatisfied_requirements", List.of(req.getType()));
                        Map<String, Object> tokenClaims = tokenClaimsMap(token);
                        String effectiveLevel = DisclosureControl.resolve(disclosureLevel, tokenClaims, disclosurePolicy);
                        failure = FailureRedaction.redact(failure, effectiveLevel);
                        Map<String, Object> resp = new LinkedHashMap<>();
                        resp.put("success", false);
                        resp.put("failure", failure);
                        resp.put("invocation_id", invocationId);
                        resp.put("client_reference_id", clientRefId);
                        resp.put("task_id", effectiveTaskId);
                        resp.put("parent_invocation_id", parentInvocationId);
                        return resp;
                    }
                }
            }

            // 4. Build invocation context.
            String rootPrincipal = token.getRootPrincipal();
            if (rootPrincipal == null || rootPrincipal.isEmpty()) {
                rootPrincipal = token.getIssuer();
            }

            InvocationContext ctx = new InvocationContext(
                    token, rootPrincipal, token.getSubject(),
                    invocationId, clientRefId,
                    effectiveTaskId, parentInvocationId,
                    token.getScope(), List.of(token.getTokenId()),
                    payload -> true // no-op for unary
            );

            // 5. Call handler.
            Map<String, Object> result;
            try {
                result = capDef.getHandler().apply(ctx, params);
            } catch (ANIPError e) {
                String sideEffectType2 = capDef.getDeclaration().getSideEffect() != null
                    ? capDef.getDeclaration().getSideEffect().getType() : null;
                appendAuditEntry(capName, token, false, e.getErrorType(),
                        Map.of("detail", e.getDetail()), null, invocationId, clientRefId,
                        effectiveTaskId, parentInvocationId, sideEffectType2);
                Map<String, Object> failure = new LinkedHashMap<>();
                failure.put("type", e.getErrorType());
                failure.put("detail", e.getDetail());
                Map<String, Object> tokenClaims = tokenClaimsMap(token);
                String effectiveLevel = DisclosureControl.resolve(disclosureLevel, tokenClaims, disclosurePolicy);
                failure = FailureRedaction.redact(failure, effectiveLevel);
                Map<String, Object> resp = new LinkedHashMap<>();
                resp.put("success", false);
                resp.put("failure", failure);
                resp.put("invocation_id", invocationId);
                resp.put("client_reference_id", clientRefId);
                resp.put("task_id", effectiveTaskId);
                resp.put("parent_invocation_id", parentInvocationId);
                return resp;
            } catch (Exception e) {
                String sideEffectType3 = capDef.getDeclaration().getSideEffect() != null
                    ? capDef.getDeclaration().getSideEffect().getType() : null;
                appendAuditEntry(capName, token, false, Constants.FAILURE_INTERNAL_ERROR,
                        null, null, invocationId, clientRefId,
                        effectiveTaskId, parentInvocationId, sideEffectType3);
                Map<String, Object> failure = new LinkedHashMap<>();
                failure.put("type", Constants.FAILURE_INTERNAL_ERROR);
                failure.put("detail", "Internal error");
                Map<String, Object> tokenClaims = tokenClaimsMap(token);
                String effectiveLevel = DisclosureControl.resolve(disclosureLevel, tokenClaims, disclosurePolicy);
                failure = FailureRedaction.redact(failure, effectiveLevel);
                Map<String, Object> resp = new LinkedHashMap<>();
                resp.put("success", false);
                resp.put("failure", failure);
                resp.put("invocation_id", invocationId);
                resp.put("client_reference_id", clientRefId);
                resp.put("task_id", effectiveTaskId);
                resp.put("parent_invocation_id", parentInvocationId);
                return resp;
            }

            // 6. Extract cost actual from context.
            CostActual costActual = ctx.getCostActual();

            // 7. Log audit (success).
            String sideEffectType4 = capDef.getDeclaration().getSideEffect() != null
                ? capDef.getDeclaration().getSideEffect().getType() : null;
            appendAuditEntry(capName, token, true, "", result, costActual, invocationId, clientRefId,
                    effectiveTaskId, parentInvocationId, sideEffectType4);

            // 8. Build response.
            Map<String, Object> resp = new LinkedHashMap<>();
            resp.put("success", true);
            resp.put("result", result);
            resp.put("invocation_id", invocationId);
            resp.put("client_reference_id", clientRefId);
            resp.put("task_id", effectiveTaskId);
            resp.put("parent_invocation_id", parentInvocationId);
            if (costActual != null) {
                resp.put("cost_actual", costActual);
            }

            // Budget context in response (v0.13).
            if (effectiveBudget != null) {
                Double costActualAmount = null;
                if (costActual != null && costActual.getFinancial() != null
                        && costActual.getFinancial().getAmount() != null) {
                    costActualAmount = costActual.getFinancial().getAmount();
                }
                String costCertainty = null;
                if (capDef.getDeclaration().getCost() != null) {
                    costCertainty = capDef.getDeclaration().getCost().getCertainty();
                }
                Map<String, Object> budgetCtx = new LinkedHashMap<>();
                budgetCtx.put("budget_max", effectiveBudget.getMaxAmount());
                budgetCtx.put("budget_currency", effectiveBudget.getCurrency());
                budgetCtx.put("cost_certainty", costCertainty);
                budgetCtx.put("within_budget", true);
                if (checkAmount != null) {
                    budgetCtx.put("cost_check_amount", checkAmount);
                }
                if (costActualAmount != null) {
                    budgetCtx.put("cost_actual", costActualAmount);
                }
                resp.put("budget_context", budgetCtx);
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

        String requestTaskId = opts != null ? opts.getTaskId() : null;
        String parentInvocationId = opts != null ? opts.getParentInvocationId() : null;

        // task_id precedence: token purpose.task_id is authoritative
        String tokenTaskId = (token.getPurpose() != null) ? token.getPurpose().getTaskId() : null;
        if (tokenTaskId != null && !tokenTaskId.isEmpty()
                && requestTaskId != null && !requestTaskId.isEmpty()
                && !requestTaskId.equals(tokenTaskId)) {
            throw new ANIPError(Constants.FAILURE_PURPOSE_MISMATCH,
                    "Request task_id '" + requestTaskId
                            + "' does not match token purpose task_id '" + tokenTaskId + "'");
        }
        String effectiveTaskId = (requestTaskId != null && !requestTaskId.isEmpty())
                ? requestTaskId : tokenTaskId;

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
            eventPayload.put("task_id", effectiveTaskId);
            eventPayload.put("parent_invocation_id", parentInvocationId);
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
                effectiveTaskId, parentInvocationId,
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
                String streamSideEffect = capDef.getDeclaration().getSideEffect() != null
                    ? capDef.getDeclaration().getSideEffect().getType() : null;
                appendAuditEntry(capName, token, true, "", result, costActual,
                        invocationId, clientRefId, effectiveTaskId, parentInvocationId,
                        streamSideEffect);

                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("invocation_id", invocationId);
                payload.put("client_reference_id", clientRefId);
                payload.put("task_id", effectiveTaskId);
                payload.put("parent_invocation_id", parentInvocationId);
                payload.put("timestamp", DateTimeFormatter.ISO_INSTANT.format(Instant.now()));
                payload.put("success", true);
                payload.put("result", result);
                payload.put("cost_actual", costActual);

                queue.put(new StreamEvent("completed", payload));
                success = true;
            } catch (ANIPError e) {
                String streamSideEffect2 = capDef.getDeclaration().getSideEffect() != null
                    ? capDef.getDeclaration().getSideEffect().getType() : null;
                appendAuditEntry(capName, token, false, e.getErrorType(),
                        Map.of("detail", e.getDetail()), null, invocationId, clientRefId,
                        effectiveTaskId, parentInvocationId, streamSideEffect2);

                Map<String, Object> failureObj = new LinkedHashMap<>();
                failureObj.put("type", e.getErrorType());
                failureObj.put("detail", e.getDetail());
                failureObj.put("retry", e.isRetry());
                failureObj.put("resolution", e.getResolution() != null
                        ? Map.of("action", e.getResolution().getAction()) : null);

                Map<String, Object> streamTokenClaims = tokenClaimsMap(token);
                String streamEffLevel = DisclosureControl.resolve(disclosureLevel, streamTokenClaims, disclosurePolicy);
                failureObj = FailureRedaction.redact(failureObj, streamEffLevel);

                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("invocation_id", invocationId);
                payload.put("client_reference_id", clientRefId);
                payload.put("task_id", effectiveTaskId);
                payload.put("parent_invocation_id", parentInvocationId);
                payload.put("timestamp", DateTimeFormatter.ISO_INSTANT.format(Instant.now()));
                payload.put("success", false);
                payload.put("failure", failureObj);

                try {
                    queue.put(new StreamEvent("failed", payload));
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                }
            } catch (Exception e) {
                String streamSideEffect3 = capDef.getDeclaration().getSideEffect() != null
                    ? capDef.getDeclaration().getSideEffect().getType() : null;
                appendAuditEntry(capName, token, false, Constants.FAILURE_INTERNAL_ERROR,
                        null, null, invocationId, clientRefId,
                        effectiveTaskId, parentInvocationId, streamSideEffect3);

                Map<String, Object> failureObj = new LinkedHashMap<>();
                failureObj.put("type", Constants.FAILURE_INTERNAL_ERROR);
                failureObj.put("detail", "Internal error");
                failureObj.put("resolution", null);
                failureObj.put("retry", false);

                Map<String, Object> streamTokenClaims2 = tokenClaimsMap(token);
                String streamEffLevel2 = DisclosureControl.resolve(disclosureLevel, streamTokenClaims2, disclosurePolicy);
                failureObj = FailureRedaction.redact(failureObj, streamEffLevel2);

                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("invocation_id", invocationId);
                payload.put("client_reference_id", clientRefId);
                payload.put("task_id", effectiveTaskId);
                payload.put("parent_invocation_id", parentInvocationId);
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
                // Scope matched — check token-evaluable control requirements.
                List<String> unmet = new ArrayList<>();
                List<ControlRequirement> controlReqs = cap.getDeclaration().getControlRequirements();
                if (controlReqs != null) {
                    for (ControlRequirement cr : controlReqs) {
                        switch (cr.getType()) {
                            case "cost_ceiling" -> {
                                if (token.getConstraints() == null || token.getConstraints().getBudget() == null) {
                                    unmet.add("cost_ceiling");
                                }
                            }
                            case "stronger_delegation_required" -> {
                                boolean tokenHasExplicitBinding = token.getPurpose() != null
                                        && name.equals(token.getPurpose().getCapability());
                                if (!tokenHasExplicitBinding) {
                                    unmet.add("stronger_delegation_required");
                                }
                            }
                        }
                    }
                }

                if (!unmet.isEmpty()) {
                    boolean hasRejectEnforcement = false;
                    if (controlReqs != null) {
                        for (ControlRequirement cr : controlReqs) {
                            if ("reject".equals(cr.getEnforcement()) && unmet.contains(cr.getType())) {
                                hasRejectEnforcement = true;
                                break;
                            }
                        }
                    }
                    if (hasRejectEnforcement) {
                        restricted.add(new PermissionResponse.RestrictedCapability(
                                name,
                                "missing control requirements: " + String.join(", ", unmet),
                                rootPrincipal,
                                unmet
                        ));
                        continue;
                    }
                }

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
                // Include constraints-level budget info if present.
                if (token.getConstraints() != null && token.getConstraints().getBudget() != null) {
                    constraints.put("budget_remaining", token.getConstraints().getBudget().getMaxAmount());
                    constraints.put("currency", token.getConstraints().getBudget().getCurrency());
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
        Map<String, Object> failureDisc = new LinkedHashMap<>();
        failureDisc.put("detail_level", disclosureLevel);
        if ("policy".equals(disclosureLevel) && disclosurePolicy != null) {
            failureDisc.put("caller_classes", new ArrayList<>(disclosurePolicy.keySet()));
        }

        doc.put("posture", Map.of(
                "audit", Map.of(
                        "retention", retentionPolicy.getDefaultRetention(),
                        "retention_enforced", retentionRunning
                ),
                "failure_disclosure", failureDisc,
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
                                   String invocationId, String clientReferenceId,
                                   String taskId, String parentInvocationId,
                                   String sideEffectType) {
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
        entry.setTaskId(taskId);
        entry.setParentInvocationId(parentInvocationId);

        // Classification + retention
        String eventClass = EventClassification.classify(sideEffectType, success, failureType);
        String tier = retentionPolicy.resolveTier(eventClass);
        String expiresAt = retentionPolicy.computeExpiresAt(tier, Instant.now());
        entry.setEventClass(eventClass);
        entry.setRetentionTier(tier);
        entry.setExpiresAt(expiresAt);

        // Storage redaction
        if (StorageRedaction.isLowValue(eventClass)) {
            entry.setParameters(null);
            entry.setStorageRedacted(true);
        }

        // Route through aggregator if applicable
        if (aggregator != null && "malformed_or_spam".equals(eventClass)) {
            aggregator.submit(entryToMap(entry));
            return;
        }

        try {
            AuditLog.appendAudit(keys, storage, entry);
            fireAuditAppend(entry.getSequenceNumber(), capability, invocationId);
        } catch (Exception ignored) {
            // Best effort -- don't fail invocation if audit logging fails.
        }
    }

    private Map<String, Object> tokenClaimsMap(DelegationToken token) {
        Map<String, Object> claims = new HashMap<>();
        claims.put("scope", token.getScope());
        if (token.getCallerClass() != null && !token.getCallerClass().isEmpty()) {
            claims.put("anip:caller_class", token.getCallerClass());
        }
        return claims;
    }

    private Map<String, Object> entryToMap(AuditEntry entry) {
        Map<String, Object> m = new HashMap<>();
        m.put("timestamp", entry.getTimestamp());
        m.put("capability", entry.getCapability());
        m.put("actor_key", entry.getRootPrincipal());
        m.put("failure_type", entry.getFailureType());
        m.put("event_class", entry.getEventClass());
        m.put("retention_tier", entry.getRetentionTier());
        m.put("expires_at", entry.getExpiresAt());
        m.put("invocation_id", entry.getInvocationId());
        m.put("client_reference_id", entry.getClientReferenceId());
        m.put("task_id", entry.getTaskId());
        m.put("parent_invocation_id", entry.getParentInvocationId());
        m.put("token_id", entry.getTokenId());
        m.put("issuer", entry.getIssuer());
        m.put("subject", entry.getSubject());
        if (entry.getResultSummary() != null) {
            Object detail = entry.getResultSummary().get("detail");
            if (detail != null) m.put("detail", detail);
        }
        return m;
    }

    private void flushAggregator() {
        if (aggregator == null) return;
        List<Object> results = aggregator.flush(Instant.now());
        for (Object item : results) {
            @SuppressWarnings("unchecked")
            Map<String, Object> entryData = StorageRedaction.redactEntry((Map<String, Object>) item);
            persistAuditMap(entryData);
        }
    }

    @SuppressWarnings("unchecked")
    private void persistAuditMap(Map<String, Object> entryData) {
        AuditEntry entry = new AuditEntry();
        entry.setCapability((String) entryData.get("capability"));
        entry.setSuccess(false);
        entry.setFailureType((String) entryData.get("failure_type"));
        entry.setEventClass((String) entryData.get("event_class"));
        entry.setRetentionTier((String) entryData.get("retention_tier"));
        entry.setExpiresAt((String) entryData.get("expires_at"));
        // Derive root principal: top-level actor_key, or from grouping_key for aggregated entries.
        String rootPrincipal = (String) entryData.get("actor_key");
        if (rootPrincipal == null && entryData.get("grouping_key") instanceof Map) {
            @SuppressWarnings("unchecked")
            Map<String, String> gk = (Map<String, String>) entryData.get("grouping_key");
            rootPrincipal = gk.get("actor_key");
        }
        entry.setRootPrincipal(rootPrincipal);
        entry.setTimestamp((String) entryData.get("timestamp"));
        entry.setInvocationId((String) entryData.get("invocation_id"));
        entry.setClientReferenceId((String) entryData.get("client_reference_id"));
        entry.setTokenId((String) entryData.get("token_id"));
        entry.setIssuer((String) entryData.get("issuer"));
        entry.setSubject((String) entryData.get("subject"));
        String entryType = (String) entryData.get("entry_type");
        entry.setEntryType(entryType != null ? entryType : "normal");
        // Aggregation fields
        if (entryData.get("grouping_key") instanceof Map) {
            entry.setGroupingKey((Map<String, String>) entryData.get("grouping_key"));
        }
        if (entryData.get("aggregation_window") instanceof Map) {
            entry.setAggregationWindow((Map<String, String>) entryData.get("aggregation_window"));
        }
        if (entryData.get("aggregation_count") instanceof Integer count) {
            entry.setAggregationCount(count);
        }
        entry.setFirstSeen((String) entryData.get("first_seen"));
        entry.setLastSeen((String) entryData.get("last_seen"));
        entry.setRepresentativeDetail((String) entryData.get("representative_detail"));
        // Restore storage redaction flag from the redacted map.
        if (Boolean.TRUE.equals(entryData.get("storage_redacted"))) {
            entry.setStorageRedacted(true);
        }
        try {
            AuditLog.appendAudit(keys, storage, entry);
        } catch (Exception ignored) {}
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

    // --- Budget / binding helper methods ---

    /**
     * Extracts a bound price from params using capability's binding declarations.
     */
    @SuppressWarnings("unchecked")
    private static Double resolveBoundPrice(List<BindingRequirement> bindings, Map<String, Object> params) {
        for (BindingRequirement binding : bindings) {
            Object v = params.get(binding.getField());
            if (v instanceof Map) {
                Map<String, Object> m = (Map<String, Object>) v;
                Object price = m.get("price");
                if (price instanceof Number n) {
                    return n.doubleValue();
                }
            }
        }
        return null;
    }

    /**
     * Determines the age of a binding value in seconds.
     * Returns -1 if age cannot be determined.
     */
    @SuppressWarnings("unchecked")
    private static long resolveBindingAge(Object bindingValue) {
        long now = System.currentTimeMillis() / 1000;
        if (bindingValue instanceof Map) {
            Map<String, Object> m = (Map<String, Object>) bindingValue;
            Object issuedAt = m.get("issued_at");
            if (issuedAt instanceof Number n) {
                return now - n.longValue();
            }
        }
        if (bindingValue instanceof String s) {
            // Try to extract unix timestamp from format like "qt-hexhex-1234567890"
            java.util.regex.Matcher matcher = java.util.regex.Pattern.compile("-(\\d{10,})$").matcher(s);
            if (matcher.find()) {
                try {
                    long ts = Long.parseLong(matcher.group(1));
                    if (ts > 1000000000) {
                        return now - ts;
                    }
                } catch (NumberFormatException ignored) {
                }
            }
        }
        return -1;
    }

    /**
     * Parses a simple ISO 8601 duration string like PT15M, PT1H30M, PT30S.
     * Returns the duration in seconds.
     */
    private static long parseISO8601DurationSeconds(String d) {
        if (d == null || d.isEmpty()) return 0;
        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile(
                "PT(?:(\\d+)H)?(?:(\\d+)M)?(?:(\\d+)S)?").matcher(d);
        if (!matcher.matches()) return 0;
        long total = 0;
        if (matcher.group(1) != null) {
            total += Long.parseLong(matcher.group(1)) * 3600;
        }
        if (matcher.group(2) != null) {
            total += Long.parseLong(matcher.group(2)) * 60;
        }
        if (matcher.group(3) != null) {
            total += Long.parseLong(matcher.group(3));
        }
        return total;
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
