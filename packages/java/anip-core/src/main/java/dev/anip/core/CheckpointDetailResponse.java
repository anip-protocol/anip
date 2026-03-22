package dev.anip.core;

import java.util.Map;

/**
 * Response from the checkpoint detail endpoint.
 */
public class CheckpointDetailResponse {

    private final Map<String, Object> checkpoint;
    private final Map<String, Object> inclusionProof;
    private final String proofUnavailable;

    public CheckpointDetailResponse(Map<String, Object> checkpoint,
                                     Map<String, Object> inclusionProof,
                                     String proofUnavailable) {
        this.checkpoint = checkpoint;
        this.inclusionProof = inclusionProof;
        this.proofUnavailable = proofUnavailable;
    }

    public Map<String, Object> getCheckpoint() {
        return checkpoint;
    }

    public Map<String, Object> getInclusionProof() {
        return inclusionProof;
    }

    public String getProofUnavailable() {
        return proofUnavailable;
    }
}
