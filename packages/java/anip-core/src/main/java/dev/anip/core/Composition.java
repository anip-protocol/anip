package dev.anip.core;

import java.util.List;
import java.util.Map;

/** Declarative composition for kind=composed capabilities. v0.23. See SPEC.md §4.6. */
public class Composition {
    private final String authorityBoundary;
    private final List<CompositionStep> steps;
    private final Map<String, Map<String, String>> inputMapping;
    private final Map<String, String> outputMapping;
    private String emptyResultPolicy;
    private Map<String, Object> emptyResultOutput;
    private final FailurePolicy failurePolicy;
    private final AuditPolicy auditPolicy;

    public Composition(String authorityBoundary,
                       List<CompositionStep> steps,
                       Map<String, Map<String, String>> inputMapping,
                       Map<String, String> outputMapping,
                       FailurePolicy failurePolicy,
                       AuditPolicy auditPolicy) {
        this.authorityBoundary = authorityBoundary;
        this.steps = steps;
        this.inputMapping = inputMapping;
        this.outputMapping = outputMapping;
        this.failurePolicy = failurePolicy;
        this.auditPolicy = auditPolicy;
    }

    public String getAuthorityBoundary() {
        return authorityBoundary;
    }

    public List<CompositionStep> getSteps() {
        return steps;
    }

    public Map<String, Map<String, String>> getInputMapping() {
        return inputMapping;
    }

    public Map<String, String> getOutputMapping() {
        return outputMapping;
    }

    public String getEmptyResultPolicy() {
        return emptyResultPolicy;
    }

    public Composition setEmptyResultPolicy(String emptyResultPolicy) {
        this.emptyResultPolicy = emptyResultPolicy;
        return this;
    }

    public Map<String, Object> getEmptyResultOutput() {
        return emptyResultOutput;
    }

    public Composition setEmptyResultOutput(Map<String, Object> emptyResultOutput) {
        this.emptyResultOutput = emptyResultOutput;
        return this;
    }

    public FailurePolicy getFailurePolicy() {
        return failurePolicy;
    }

    public AuditPolicy getAuditPolicy() {
        return auditPolicy;
    }
}
