package dev.anip.core;

/**
 * The server's invocation response.
 */
public class InvokeResponse {

    private final boolean success;
    private final String invocationId;
    private final String clientReferenceId;
    private final Object result;
    private final CostActual costActual;
    private final ANIPError failure;

    public InvokeResponse(boolean success, String invocationId, String clientReferenceId,
                          Object result, CostActual costActual, ANIPError failure) {
        this.success = success;
        this.invocationId = invocationId;
        this.clientReferenceId = clientReferenceId;
        this.result = result;
        this.costActual = costActual;
        this.failure = failure;
    }

    public boolean isSuccess() {
        return success;
    }

    public String getInvocationId() {
        return invocationId;
    }

    public String getClientReferenceId() {
        return clientReferenceId;
    }

    public Object getResult() {
        return result;
    }

    public CostActual getCostActual() {
        return costActual;
    }

    public ANIPError getFailure() {
        return failure;
    }
}
