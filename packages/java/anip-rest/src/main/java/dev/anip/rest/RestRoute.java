package dev.anip.rest;

import dev.anip.core.CapabilityDeclaration;

/**
 * A single REST endpoint generated from an ANIP capability.
 */
public class RestRoute {

    private final String capabilityName;
    private final String path;
    private final String method; // "GET" or "POST"
    private final CapabilityDeclaration declaration;

    public RestRoute(String capabilityName, String path, String method,
                     CapabilityDeclaration declaration) {
        this.capabilityName = capabilityName;
        this.path = path;
        this.method = method;
        this.declaration = declaration;
    }

    public String getCapabilityName() {
        return capabilityName;
    }

    public String getPath() {
        return path;
    }

    public String getMethod() {
        return method;
    }

    public CapabilityDeclaration getDeclaration() {
        return declaration;
    }
}
