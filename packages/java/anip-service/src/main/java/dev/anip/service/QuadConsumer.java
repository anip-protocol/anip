package dev.anip.service;

/**
 * A functional interface that accepts four arguments and returns no result.
 */
@FunctionalInterface
public interface QuadConsumer<A, B, C, D> {
    void accept(A a, B b, C c, D d);
}
