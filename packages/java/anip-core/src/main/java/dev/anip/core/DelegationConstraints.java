package dev.anip.core;

/**
 * Constrains how delegation tokens can be sub-delegated.
 */
public class DelegationConstraints {

    private final int maxDelegationDepth;
    private final String concurrentBranches;

    public DelegationConstraints(int maxDelegationDepth, String concurrentBranches) {
        this.maxDelegationDepth = maxDelegationDepth;
        this.concurrentBranches = concurrentBranches;
    }

    /** Creates constraints with default values (depth 3, concurrent allowed). */
    public DelegationConstraints() {
        this(3, "allowed");
    }

    /** Maximum depth of delegation chain. */
    public int getMaxDelegationDepth() {
        return maxDelegationDepth;
    }

    /** "allowed" or "exclusive". */
    public String getConcurrentBranches() {
        return concurrentBranches;
    }
}
