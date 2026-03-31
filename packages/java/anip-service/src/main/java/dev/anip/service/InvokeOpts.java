package dev.anip.service;

/**
 * Optional parameters for invocation.
 */
public class InvokeOpts {

    private String clientReferenceId;
    private boolean stream;
    private String taskId;
    private String parentInvocationId;

    public InvokeOpts() {}

    public InvokeOpts(String clientReferenceId, boolean stream) {
        this.clientReferenceId = clientReferenceId;
        this.stream = stream;
    }

    public InvokeOpts(String clientReferenceId, boolean stream, String taskId, String parentInvocationId) {
        this.clientReferenceId = clientReferenceId;
        this.stream = stream;
        this.taskId = taskId;
        this.parentInvocationId = parentInvocationId;
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

    public String getTaskId() {
        return taskId;
    }

    public InvokeOpts setTaskId(String taskId) {
        this.taskId = taskId;
        return this;
    }

    public String getParentInvocationId() {
        return parentInvocationId;
    }

    public InvokeOpts setParentInvocationId(String parentInvocationId) {
        this.parentInvocationId = parentInvocationId;
        return this;
    }
}
