package dev.anip.service;

import dev.anip.core.CostActual;
import dev.anip.core.DelegationToken;

import java.util.List;
import java.util.Map;
import java.util.function.Function;

/**
 * Provides the handler with delegation context for an invocation.
 */
public class InvocationContext {

    private final DelegationToken token;
    private final String rootPrincipal;
    private final String subject;
    private final String invocationId;
    private final String clientReferenceId;
    private final String taskId;
    private final String parentInvocationId;
    private final String upstreamService;
    private final List<String> scopes;
    private final List<String> delegationChain;
    private final Function<Map<String, Object>, Boolean> emitProgress;
    private CostActual costActual;

    public InvocationContext(DelegationToken token, String rootPrincipal, String subject,
                             String invocationId, String clientReferenceId,
                             List<String> scopes, List<String> delegationChain,
                             Function<Map<String, Object>, Boolean> emitProgress) {
        this(token, rootPrincipal, subject, invocationId, clientReferenceId,
                null, null, scopes, delegationChain, emitProgress);
    }

    public InvocationContext(DelegationToken token, String rootPrincipal, String subject,
                             String invocationId, String clientReferenceId,
                             String taskId, String parentInvocationId,
                             List<String> scopes, List<String> delegationChain,
                             Function<Map<String, Object>, Boolean> emitProgress) {
        this(token, rootPrincipal, subject, invocationId, clientReferenceId,
                taskId, parentInvocationId, null, scopes, delegationChain, emitProgress);
    }

    public InvocationContext(DelegationToken token, String rootPrincipal, String subject,
                             String invocationId, String clientReferenceId,
                             String taskId, String parentInvocationId, String upstreamService,
                             List<String> scopes, List<String> delegationChain,
                             Function<Map<String, Object>, Boolean> emitProgress) {
        this.token = token;
        this.rootPrincipal = rootPrincipal;
        this.subject = subject;
        this.invocationId = invocationId;
        this.clientReferenceId = clientReferenceId;
        this.taskId = taskId;
        this.parentInvocationId = parentInvocationId;
        this.upstreamService = upstreamService;
        this.scopes = scopes;
        this.delegationChain = delegationChain;
        this.emitProgress = emitProgress;
    }

    public DelegationToken getToken() {
        return token;
    }

    public String getRootPrincipal() {
        return rootPrincipal;
    }

    public String getSubject() {
        return subject;
    }

    public String getInvocationId() {
        return invocationId;
    }

    public String getClientReferenceId() {
        return clientReferenceId;
    }

    public String getTaskId() {
        return taskId;
    }

    public String getParentInvocationId() {
        return parentInvocationId;
    }

    public String getUpstreamService() {
        return upstreamService;
    }

    public List<String> getScopes() {
        return scopes;
    }

    public List<String> getDelegationChain() {
        return delegationChain;
    }

    public Function<Map<String, Object>, Boolean> getEmitProgress() {
        return emitProgress;
    }

    public void setCostActual(CostActual cost) {
        this.costActual = cost;
    }

    public CostActual getCostActual() {
        return costActual;
    }
}
