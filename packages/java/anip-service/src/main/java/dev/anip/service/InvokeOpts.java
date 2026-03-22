package dev.anip.service;

/**
 * Optional parameters for invocation.
 */
public class InvokeOpts {

    private String clientReferenceId;
    private boolean stream;

    public InvokeOpts() {}

    public InvokeOpts(String clientReferenceId, boolean stream) {
        this.clientReferenceId = clientReferenceId;
        this.stream = stream;
    }

    public String getClientReferenceId() {
        return clientReferenceId;
    }

    public InvokeOpts setClientReferenceId(String clientReferenceId) {
        this.clientReferenceId = clientReferenceId;
        return this;
    }

    public boolean isStream() {
        return stream;
    }

    public InvokeOpts setStream(boolean stream) {
        this.stream = stream;
        return this;
    }
}
