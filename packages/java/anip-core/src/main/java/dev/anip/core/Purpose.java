package dev.anip.core;

import java.util.Map;

/**
 * Describes the intended use of a delegation token.
 */
public class Purpose {

    private final String capability;
    private final Map<String, Object> parameters;
    private final String taskId;

    public Purpose(String capability, Map<String, Object> parameters, String taskId) {
        this.capability = capability;
        this.parameters = parameters;
        this.taskId = taskId;
    }

    public String getCapability() {
        return capability;
    }

    public Map<String, Object> getParameters() {
        return parameters;
    }

    public String getTaskId() {
        return taskId;
    }
}
