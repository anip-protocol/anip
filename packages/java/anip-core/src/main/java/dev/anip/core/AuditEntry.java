package dev.anip.core;

import java.util.List;
import java.util.Map;

/**
 * A single audit log record.
 */
public class AuditEntry {

    private int sequenceNumber;
    private String timestamp;
    private String capability;
    private String tokenId;
    private String issuer;
    private String subject;
    private String rootPrincipal;
    private Map<String, Object> parameters;
    private boolean success;
    private Map<String, Object> resultSummary;
    private String failureType;
    private CostActual costActual;
    private List<String> delegationChain;
    private String invocationId;
    private String clientReferenceId;
    private String previousHash;
    private String signature;
    private String eventClass;
    private String retentionTier;
    private String expiresAt;
    private boolean storageRedacted;
    private String entryType;
    private Map<String, Object> streamSummary;

    public AuditEntry() {}

    public int getSequenceNumber() { return sequenceNumber; }
    public void setSequenceNumber(int sequenceNumber) { this.sequenceNumber = sequenceNumber; }

    public String getTimestamp() { return timestamp; }
    public void setTimestamp(String timestamp) { this.timestamp = timestamp; }

    public String getCapability() { return capability; }
    public void setCapability(String capability) { this.capability = capability; }

    public String getTokenId() { return tokenId; }
    public void setTokenId(String tokenId) { this.tokenId = tokenId; }

    public String getIssuer() { return issuer; }
    public void setIssuer(String issuer) { this.issuer = issuer; }

    public String getSubject() { return subject; }
    public void setSubject(String subject) { this.subject = subject; }

    public String getRootPrincipal() { return rootPrincipal; }
    public void setRootPrincipal(String rootPrincipal) { this.rootPrincipal = rootPrincipal; }

    public Map<String, Object> getParameters() { return parameters; }
    public void setParameters(Map<String, Object> parameters) { this.parameters = parameters; }

    public boolean isSuccess() { return success; }
    public void setSuccess(boolean success) { this.success = success; }

    public Map<String, Object> getResultSummary() { return resultSummary; }
    public void setResultSummary(Map<String, Object> resultSummary) { this.resultSummary = resultSummary; }

    public String getFailureType() { return failureType; }
    public void setFailureType(String failureType) { this.failureType = failureType; }

    public CostActual getCostActual() { return costActual; }
    public void setCostActual(CostActual costActual) { this.costActual = costActual; }

    public List<String> getDelegationChain() { return delegationChain; }
    public void setDelegationChain(List<String> delegationChain) { this.delegationChain = delegationChain; }

    public String getInvocationId() { return invocationId; }
    public void setInvocationId(String invocationId) { this.invocationId = invocationId; }

    public String getClientReferenceId() { return clientReferenceId; }
    public void setClientReferenceId(String clientReferenceId) { this.clientReferenceId = clientReferenceId; }

    public String getPreviousHash() { return previousHash; }
    public void setPreviousHash(String previousHash) { this.previousHash = previousHash; }

    public String getSignature() { return signature; }
    public void setSignature(String signature) { this.signature = signature; }

    public String getEventClass() { return eventClass; }
    public void setEventClass(String eventClass) { this.eventClass = eventClass; }

    public String getRetentionTier() { return retentionTier; }
    public void setRetentionTier(String retentionTier) { this.retentionTier = retentionTier; }

    public String getExpiresAt() { return expiresAt; }
    public void setExpiresAt(String expiresAt) { this.expiresAt = expiresAt; }

    public boolean isStorageRedacted() { return storageRedacted; }
    public void setStorageRedacted(boolean storageRedacted) { this.storageRedacted = storageRedacted; }

    public String getEntryType() { return entryType; }
    public void setEntryType(String entryType) { this.entryType = entryType; }

    public Map<String, Object> getStreamSummary() { return streamSummary; }
    public void setStreamSummary(Map<String, Object> streamSummary) { this.streamSummary = streamSummary; }
}
