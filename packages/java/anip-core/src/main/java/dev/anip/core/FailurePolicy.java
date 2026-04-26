package dev.anip.core;

/** Per-child-outcome failure handling for composed capabilities. v0.23. See SPEC.md §4.6. */
public class FailurePolicy {
    private String childClarification = "propagate";
    private String childDenial = "propagate";
    private String childApprovalRequired = "propagate";
    private String childError = "fail_parent";

    public FailurePolicy() {}

    public FailurePolicy(String childClarification, String childDenial,
                         String childApprovalRequired, String childError) {
        this.childClarification = childClarification;
        this.childDenial = childDenial;
        this.childApprovalRequired = childApprovalRequired;
        this.childError = childError;
    }

    public String getChildClarification() {
        return childClarification;
    }

    public String getChildDenial() {
        return childDenial;
    }

    public String getChildApprovalRequired() {
        return childApprovalRequired;
    }

    public String getChildError() {
        return childError;
    }
}
