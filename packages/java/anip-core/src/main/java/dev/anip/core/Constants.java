package dev.anip.core;

import java.security.SecureRandom;
import java.util.Map;

/**
 * Protocol constants for the ANIP runtime.
 */
public final class Constants {

    private Constants() {}

    /** Current ANIP protocol version. */
    public static final String PROTOCOL_VERSION = "anip/0.15";

    /** Current manifest metadata version. */
    public static final String MANIFEST_VERSION = "0.10.0";

    // Failure type constants.
    public static final String FAILURE_AUTH_REQUIRED = "authentication_required";
    public static final String FAILURE_INVALID_TOKEN = "invalid_token";
    public static final String FAILURE_TOKEN_EXPIRED = "token_expired";
    public static final String FAILURE_SCOPE_INSUFFICIENT = "scope_insufficient";
    public static final String FAILURE_UNKNOWN_CAPABILITY = "unknown_capability";
    public static final String FAILURE_BUDGET_EXCEEDED = "budget_exceeded";
    public static final String FAILURE_BUDGET_CURRENCY_MISMATCH = "budget_currency_mismatch";
    public static final String FAILURE_BUDGET_NOT_ENFORCEABLE = "budget_not_enforceable";
    public static final String FAILURE_BINDING_MISSING = "binding_missing";
    public static final String FAILURE_BINDING_STALE = "binding_stale";
    public static final String FAILURE_CONTROL_REQUIREMENT_UNSATISFIED = "control_requirement_unsatisfied";
    public static final String FAILURE_PURPOSE_MISMATCH = "purpose_mismatch";
    public static final String FAILURE_SCOPE_ESCALATION = "scope_escalation";
    public static final String FAILURE_NOT_FOUND = "not_found";
    public static final String FAILURE_UNAVAILABLE = "unavailable";
    public static final String FAILURE_CONCURRENT_LOCK = "concurrent_lock";
    public static final String FAILURE_INTERNAL_ERROR = "internal_error";
    public static final String FAILURE_STREAMING_NOT_SUPPORTED = "streaming_not_supported";
    public static final String FAILURE_INVALID_PARAMETERS = "invalid_parameters";
    public static final String FAILURE_NON_DELEGABLE_ACTION = "non_delegable_action";

    /** Maps each canonical resolution action to its recovery class. */
    public static final Map<String, String> RECOVERY_CLASS_MAP = Map.ofEntries(
            Map.entry("retry_now", "retry_now"),
            Map.entry("wait_and_retry", "wait_then_retry"),
            Map.entry("obtain_binding", "refresh_then_retry"),
            Map.entry("refresh_binding", "refresh_then_retry"),
            Map.entry("obtain_quote_first", "refresh_then_retry"),
            Map.entry("revalidate_state", "revalidate_then_retry"),
            Map.entry("request_broader_scope", "redelegation_then_retry"),
            Map.entry("request_budget_increase", "redelegation_then_retry"),
            Map.entry("request_budget_bound_delegation", "redelegation_then_retry"),
            Map.entry("request_matching_currency_delegation", "redelegation_then_retry"),
            Map.entry("request_new_delegation", "redelegation_then_retry"),
            Map.entry("request_capability_binding", "redelegation_then_retry"),
            Map.entry("request_deeper_delegation", "redelegation_then_retry"),
            Map.entry("escalate_to_root_principal", "terminal"),
            Map.entry("provide_credentials", "retry_now"),
            Map.entry("check_manifest", "revalidate_then_retry"),
            Map.entry("contact_service_owner", "terminal"),
            Map.entry("narrow_scope", "terminal"),
            Map.entry("preserve_budget_constraint", "terminal"),
            Map.entry("narrow_budget", "terminal"),
            Map.entry("match_parent_currency", "terminal"),
            Map.entry("register_missing_ancestor", "redelegation_then_retry"),
            Map.entry("reduce_delegation_depth", "terminal"),
            Map.entry("refresh_delegation_chain", "redelegation_then_retry"),
            Map.entry("register_parent_token_first", "redelegation_then_retry"),
            Map.entry("narrow_constraints", "terminal"),
            Map.entry("preserve_constraint", "terminal"),
            Map.entry("register_token", "redelegation_then_retry"),
            Map.entry("use_token_task_id", "revalidate_then_retry"),
            Map.entry("provide_priced_binding", "refresh_then_retry"),
            Map.entry("list_checkpoints", "revalidate_then_retry")
    );

    /**
     * Returns the recovery class for a given action.
     * Throws IllegalArgumentException if the action is not in the map.
     */
    public static String recoveryClassForAction(String action) {
        String cls = RECOVERY_CLASS_MAP.get(action);
        if (cls == null) {
            throw new IllegalArgumentException("No recovery class mapped for action: \"" + action + "\"");
        }
        return cls;
    }

    /** Supported algorithms for signing. */
    public static final String[] SUPPORTED_ALGORITHMS = {"ES256"};

    /** Merkle tree hash prefixes per RFC 6962. */
    public static final byte LEAF_HASH_PREFIX = 0x00;
    public static final byte NODE_HASH_PREFIX = 0x01;

    /** Default ANIP profile version set. */
    public static final Map<String, String> DEFAULT_PROFILE = Map.of(
            "core", "1.0",
            "cost", "1.0",
            "capability_graph", "1.0",
            "state_session", "1.0",
            "observability", "1.0"
    );

    private static final SecureRandom RANDOM = new SecureRandom();

    /**
     * Generates a new invocation ID in the format {@code inv-{12 hex chars}}.
     */
    public static String generateInvocationId() {
        byte[] bytes = new byte[6];
        RANDOM.nextBytes(bytes);
        StringBuilder sb = new StringBuilder("inv-");
        for (byte b : bytes) {
            sb.append(String.format("%02x", b & 0xff));
        }
        return sb.toString();
    }

    /**
     * Maps failure types to HTTP status codes.
     */
    public static int failureStatusCode(String failureType) {
        if (failureType == null) {
            return 400;
        }
        return switch (failureType) {
            case FAILURE_AUTH_REQUIRED, FAILURE_INVALID_TOKEN, FAILURE_TOKEN_EXPIRED -> 401;
            case FAILURE_SCOPE_INSUFFICIENT, FAILURE_BUDGET_EXCEEDED,
                 FAILURE_BUDGET_CURRENCY_MISMATCH, FAILURE_BUDGET_NOT_ENFORCEABLE,
                 FAILURE_BINDING_MISSING, FAILURE_BINDING_STALE,
                 FAILURE_CONTROL_REQUIREMENT_UNSATISFIED,
                 FAILURE_PURPOSE_MISMATCH, FAILURE_SCOPE_ESCALATION -> 403;
            case FAILURE_UNKNOWN_CAPABILITY, FAILURE_NOT_FOUND -> 404;
            case FAILURE_UNAVAILABLE, FAILURE_CONCURRENT_LOCK -> 409;
            case FAILURE_INTERNAL_ERROR -> 500;
            case FAILURE_INVALID_PARAMETERS -> 400;
            default -> 400;
        };
    }
}
