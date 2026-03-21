package dev.anip.service;

import dev.anip.core.CapabilityDeclaration;

import java.util.Map;
import java.util.function.BiFunction;

/**
 * Binds a capability declaration to a handler function.
 */
public class CapabilityDef {

    private final CapabilityDeclaration declaration;
    private final BiFunction<InvocationContext, Map<String, Object>, Map<String, Object>> handler;

    public CapabilityDef(CapabilityDeclaration declaration,
                         BiFunction<InvocationContext, Map<String, Object>, Map<String, Object>> handler) {
        this.declaration = declaration;
        this.handler = handler;
    }

    public CapabilityDeclaration getDeclaration() {
        return declaration;
    }

    public BiFunction<InvocationContext, Map<String, Object>, Map<String, Object>> getHandler() {
        return handler;
    }
}
