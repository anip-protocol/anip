package dev.anip.service;

/**
 * Optional callbacks for logging, metrics, and tracing.
 * All hooks are nullable -- check before calling. Wrapped in try-catch
 * so handler panics never affect correctness.
 */
public class ObservabilityHooks {

    // Logging hooks
    private TriConsumer<String, String, String> onTokenIssued;         // tokenId, subject, capability
    private java.util.function.BiConsumer<String, String> onTokenResolved;  // tokenId, subject
    private TriConsumer<String, String, String> onInvokeStart;         // invocationId, capability, subject
    private QuadConsumer<String, String, Boolean, Long> onInvokeComplete;  // invocationId, capability, success, durationMs
    private TriConsumer<Integer, String, String> onAuditAppend;        // seqNum, capability, invocationId
    private java.util.function.BiConsumer<String, Integer> onCheckpointCreated; // checkpointId, entryCount
    private java.util.function.BiConsumer<String, String> onAuthFailure;    // failureType, detail
    private java.util.function.BiConsumer<String, Boolean> onScopeValidation; // capability, granted

    // Metrics hooks
    private TriConsumer<String, Long, Boolean> onInvokeDuration;       // capability, durationMs, success

    public ObservabilityHooks() {}

    // --- Getters and setters ---

    public TriConsumer<String, String, String> getOnTokenIssued() {
        return onTokenIssued;
    }

    public ObservabilityHooks setOnTokenIssued(TriConsumer<String, String, String> onTokenIssued) {
        this.onTokenIssued = onTokenIssued;
        return this;
    }

    public java.util.function.BiConsumer<String, String> getOnTokenResolved() {
        return onTokenResolved;
    }

    public ObservabilityHooks setOnTokenResolved(java.util.function.BiConsumer<String, String> onTokenResolved) {
        this.onTokenResolved = onTokenResolved;
        return this;
    }

    public TriConsumer<String, String, String> getOnInvokeStart() {
        return onInvokeStart;
    }

    public ObservabilityHooks setOnInvokeStart(TriConsumer<String, String, String> onInvokeStart) {
        this.onInvokeStart = onInvokeStart;
        return this;
    }

    public QuadConsumer<String, String, Boolean, Long> getOnInvokeComplete() {
        return onInvokeComplete;
    }

    public ObservabilityHooks setOnInvokeComplete(QuadConsumer<String, String, Boolean, Long> onInvokeComplete) {
        this.onInvokeComplete = onInvokeComplete;
        return this;
    }

    public TriConsumer<Integer, String, String> getOnAuditAppend() {
        return onAuditAppend;
    }

    public ObservabilityHooks setOnAuditAppend(TriConsumer<Integer, String, String> onAuditAppend) {
        this.onAuditAppend = onAuditAppend;
        return this;
    }

    public java.util.function.BiConsumer<String, Integer> getOnCheckpointCreated() {
        return onCheckpointCreated;
    }

    public ObservabilityHooks setOnCheckpointCreated(java.util.function.BiConsumer<String, Integer> onCheckpointCreated) {
        this.onCheckpointCreated = onCheckpointCreated;
        return this;
    }

    public java.util.function.BiConsumer<String, String> getOnAuthFailure() {
        return onAuthFailure;
    }

    public ObservabilityHooks setOnAuthFailure(java.util.function.BiConsumer<String, String> onAuthFailure) {
        this.onAuthFailure = onAuthFailure;
        return this;
    }

    public java.util.function.BiConsumer<String, Boolean> getOnScopeValidation() {
        return onScopeValidation;
    }

    public ObservabilityHooks setOnScopeValidation(java.util.function.BiConsumer<String, Boolean> onScopeValidation) {
        this.onScopeValidation = onScopeValidation;
        return this;
    }

    public TriConsumer<String, Long, Boolean> getOnInvokeDuration() {
        return onInvokeDuration;
    }

    public ObservabilityHooks setOnInvokeDuration(TriConsumer<String, Long, Boolean> onInvokeDuration) {
        this.onInvokeDuration = onInvokeDuration;
        return this;
    }
}
