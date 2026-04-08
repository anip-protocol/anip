/**
 * Lightweight signal implementation for use in services.
 *
 * In a real Angular 17+ application, replace these with Angular's built-in
 * `signal()` from `@angular/core`. This portable implementation allows
 * the services to be tested with vitest without an Angular test harness
 * while maintaining the same API shape.
 *
 * Angular signals have:
 *   - `signal.value` or `signal()` to read
 *   - `signal.set(newValue)` to write
 *   - `signal.update(fn)` to update based on current value
 *
 * We implement a minimal version of this interface.
 */

export interface WritableSignal<T> {
  (): T;
  set(value: T): void;
  update(fn: (current: T) => T): void;
}

export function signal<T>(initialValue: T): WritableSignal<T> {
  let current = initialValue;

  const read = (() => current) as WritableSignal<T>;

  read.set = (value: T) => {
    current = value;
  };

  read.update = (fn: (current: T) => T) => {
    current = fn(current);
  };

  return read;
}
