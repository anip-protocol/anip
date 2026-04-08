/**
 * Angular services wrapping @anip-dev/client.
 *
 * Each service provides signal-based reactive state and action methods
 * that call the underlying ANIPClient. All protocol logic lives in
 * @anip-dev/client — these services only add reactive state management.
 *
 * Uses a signal implementation matching the Angular 17+ signal API.
 * The signal interface (read/set/update) is identical to `@angular/core`'s
 * `signal()`, so these services work natively in Angular templates and
 * computed/effect contexts.
 */

import { ANIPClient } from "@anip-dev/client";
import type { ANIPClientOptions } from "@anip-dev/client";
import type {
  NormalizedDiscovery,
  NormalizedManifest,
  NormalizedCapability,
  NormalizedPermissions,
  NormalizedInvocationResult,
  NormalizedFailure,
  NormalizedAuditResult,
} from "@anip-dev/client";
import { signal, type WritableSignal } from "./signal.js";

// ---------------------------------------------------------------------------
// AnipClientService
// ---------------------------------------------------------------------------

export class AnipClientService {
  private _client: ANIPClient;

  constructor(baseUrl: string, timeout?: number) {
    const opts: ANIPClientOptions | undefined = timeout
      ? { timeout }
      : undefined;
    this._client = new ANIPClient(baseUrl, opts);
  }

  get client(): ANIPClient {
    return this._client;
  }

  setBaseUrl(url: string): void {
    this._client.setBaseUrl(url);
  }
}

// ---------------------------------------------------------------------------
// AnipDiscoveryService
// ---------------------------------------------------------------------------

export class AnipDiscoveryService {
  readonly data: WritableSignal<NormalizedDiscovery | null> = signal(null);
  readonly loading: WritableSignal<boolean> = signal(false);
  readonly error: WritableSignal<string | null> = signal(null);

  constructor(private readonly clientService: AnipClientService) {}

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const result = await this.clientService.client.discover();
      this.data.set(result);
    } catch (e: any) {
      this.data.set(null);
      this.error.set(e.message ?? "Discovery failed");
    } finally {
      this.loading.set(false);
    }
  }
}

// ---------------------------------------------------------------------------
// AnipManifestService
// ---------------------------------------------------------------------------

export class AnipManifestService {
  readonly data: WritableSignal<NormalizedManifest | null> = signal(null);
  readonly loading: WritableSignal<boolean> = signal(false);
  readonly error: WritableSignal<string | null> = signal(null);

  constructor(private readonly clientService: AnipClientService) {}

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const result = await this.clientService.client.getManifest();
      this.data.set(result);
    } catch (e: any) {
      this.data.set(null);
      this.error.set(e.message ?? "Manifest loading failed");
    } finally {
      this.loading.set(false);
    }
  }
}

// ---------------------------------------------------------------------------
// AnipCapabilityService
// ---------------------------------------------------------------------------

/**
 * Resolves a single capability from the cached manifest.
 *
 * When constructed with a manifest service's `data` signal, capability
 * state auto-updates whenever the manifest changes — no manual refresh needed.
 *
 * Usage:
 *   const capSvc = new AnipCapabilityService(clientSvc, manifestSvc.data);
 *   capSvc.resolve('book_flight');
 *   // capSvc.data() auto-updates when manifest is reloaded
 */
export class AnipCapabilityService {
  readonly data: WritableSignal<NormalizedCapability | null> = signal(null);
  private currentName: string | null = null;
  private unsubscribe: (() => void) | null = null;

  constructor(
    private readonly clientService: AnipClientService,
    manifestSignal?: WritableSignal<NormalizedManifest | null>,
  ) {
    // Auto-resolve when the manifest signal changes
    if (manifestSignal && (manifestSignal as any).__subscribe) {
      this.unsubscribe = (manifestSignal as any).__subscribe(() => {
        if (this.currentName) {
          this.data.set(this.clientService.client.getCapability(this.currentName));
        }
      });
    }
  }

  resolve(name: string): void {
    this.currentName = name;
    this.data.set(this.clientService.client.getCapability(name));
  }

  destroy(): void {
    if (this.unsubscribe) {
      this.unsubscribe();
      this.unsubscribe = null;
    }
  }
}

// ---------------------------------------------------------------------------
// AnipPermissionsService
// ---------------------------------------------------------------------------

export class AnipPermissionsService {
  readonly data: WritableSignal<NormalizedPermissions | null> = signal(null);
  readonly loading: WritableSignal<boolean> = signal(false);
  readonly error: WritableSignal<string | null> = signal(null);

  constructor(private readonly clientService: AnipClientService) {}

  async query(token: string): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const result = await this.clientService.client.queryPermissions(token);
      this.data.set(result);
    } catch (e: any) {
      this.data.set(null);
      this.error.set(e.message ?? "Permissions query failed");
    } finally {
      this.loading.set(false);
    }
  }
}

// ---------------------------------------------------------------------------
// AnipInvokeService
// ---------------------------------------------------------------------------

export class AnipInvokeService {
  readonly result: WritableSignal<NormalizedInvocationResult | null> = signal(null);
  readonly loading: WritableSignal<boolean> = signal(false);
  readonly error: WritableSignal<string | null> = signal(null);

  constructor(private readonly clientService: AnipClientService) {}

  clear(): void {
    this.result.set(null);
    this.error.set(null);
  }

  async invoke(
    token: string,
    capability: string,
    params: Record<string, unknown>,
    opts?: {
      taskId?: string;
      parentInvocationId?: string;
      clientReferenceId?: string;
    },
  ): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const res = await this.clientService.client.invoke(
        token,
        capability,
        params,
        opts,
      );
      this.result.set(res);
    } catch (e: any) {
      this.result.set(null);
      this.error.set(e.message ?? "Invocation failed");
    } finally {
      this.loading.set(false);
    }
  }
}

// ---------------------------------------------------------------------------
// AnipAuditService
// ---------------------------------------------------------------------------

export class AnipAuditService {
  readonly data: WritableSignal<NormalizedAuditResult | null> = signal(null);
  readonly loading: WritableSignal<boolean> = signal(false);
  readonly error: WritableSignal<string | null> = signal(null);

  constructor(private readonly clientService: AnipClientService) {}

  async query(
    token: string,
    filters?: {
      capability?: string;
      since?: string;
      invocationId?: string;
      clientReferenceId?: string;
      taskId?: string;
      parentInvocationId?: string;
      eventClass?: string;
      limit?: number;
    },
  ): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const res = await this.clientService.client.queryAudit(token, filters);
      this.data.set(res);
    } catch (e: any) {
      this.data.set(null);
      this.error.set(e.message ?? "Audit query failed");
    } finally {
      this.loading.set(false);
    }
  }
}

// ---------------------------------------------------------------------------
// AnipFailureService
// ---------------------------------------------------------------------------

export class AnipFailureService {
  readonly failure: WritableSignal<NormalizedFailure | null> = signal(null);

  clear(): void {
    this.failure.set(null);
  }

  setFromResult(result: NormalizedInvocationResult): void {
    this.failure.set(result.failure ?? null);
  }
}
