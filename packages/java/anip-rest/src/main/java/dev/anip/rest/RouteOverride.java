package dev.anip.rest;

/**
 * Allows customizing the path and/or method for a capability route.
 */
public class RouteOverride {

    private final String path;
    private final String method;

    public RouteOverride(String path, String method) {
        this.path = path;
        this.method = method;
    }

    public String getPath() {
        return path;
    }

    public String getMethod() {
        return method;
    }
}
