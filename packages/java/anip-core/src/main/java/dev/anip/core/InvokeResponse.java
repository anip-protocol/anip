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
    private final BudgetContext budgetContext;

    public InvokeResponse(boolean success, String invocationId, String clientReferenceId,
                          Object result, CostActual costActual, ANIPError failure) {
        this(success, invocationId, clientReferenceId, result, costActual, failure, null);
    }

    public InvokeResponse(boolean success, String invocationId, String clientReferenceId,
                          Object result, CostActual costActual, ANIPError failure,
                          BudgetContext budgetContext) {
        this.success = success;
        this.invocationId = invocationId;
        this.clientReferenceId = clientReferenceId;
        this.result = result;
        this.costActual = costActual;
        this.failure = failure;
        this.budgetContext = budgetContext;
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

    public BudgetContext getBudgetContext() {
        return budgetContext;
    }
}
