/**
 * Signal implementation matching the Angular 17+ signal API.
 *
 * This module provides a portable `signal()` that works identically to
 * Angular's `@angular/core` `signal()` — same read/set/update interface.
 * It exists so the ANIP services can be tested with vitest without a full
 * Angular test harness, while exposing the exact same API shape that
 * Angular components consume.
 *
 * In Angular apps, these signals work natively in templates, computed(),
 * and effect() because the interface is identical.
 */

export interface WritableSignal<T> {
  (): T;
  set(value: T): void;
  update(fn: (current: T) => T): void;
}

export function signal<T>(initialValue: T): WritableSignal<T> {
  let current = initialValue;
  const listeners: Array<() => void> = [];

  const read = (() => current) as WritableSignal<T>;

  read.set = (value: T) => {
    current = value;
    for (const fn of listeners) fn();
  };

  read.update = (fn: (current: T) => T) => {
    current = fn(current);
    for (const fn of listeners) fn();
  };

  // Internal: subscribe to changes (used by AnipCapabilityService)
  (read as any).__subscribe = (fn: () => void) => {
    listeners.push(fn);
    return () => {
      const idx = listeners.indexOf(fn);
      if (idx >= 0) listeners.splice(idx, 1);
    };
  };

  return read;
}
