package dev.anip.core;

/**
 * Constrains how delegation tokens can be sub-delegated.
 */
public class DelegationConstraints {

    private final int maxDelegationDepth;
    private final String concurrentBranches;
    private final Budget budget;

    public DelegationConstraints(int maxDelegationDepth, String concurrentBranches) {
        this(maxDelegationDepth, concurrentBranches, null);
    }

    public DelegationConstraints(int maxDelegationDepth, String concurrentBranches, Budget budget) {
        this.maxDelegationDepth = maxDelegationDepth;
        this.concurrentBranches = concurrentBranches;
        this.budget = budget;
    }

    /** Creates constraints with default values (depth 3, concurrent allowed). */
    public DelegationConstraints() {
        this(3, "allowed", null);
    }

    /** Maximum depth of delegation chain. */
    public int getMaxDelegationDepth() {
        return maxDelegationDepth;
    }

    /** "allowed" or "exclusive". */
    public String getConcurrentBranches() {
        return concurrentBranches;
    }

    /** Budget constraint, or null if no budget. */
    public Budget getBudget() {
        return budget;
    }
}
