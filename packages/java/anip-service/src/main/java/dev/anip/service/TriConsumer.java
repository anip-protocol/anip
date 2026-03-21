package dev.anip.service;

/**
 * A functional interface that accepts three arguments and returns no result.
 */
@FunctionalInterface
public interface TriConsumer<A, B, C> {
    void accept(A a, B b, C c);
}
