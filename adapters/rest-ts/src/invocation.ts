/**
 * ANIP capability invocation from REST requests.
 *
 * Passes caller-provided credentials (delegation token or API key)
 * through to the ANIP service. The adapter holds no tokens of its own.
 */

import type { ANIPService } from "./discovery.js";

export class CredentialError extends Error {
  constructor() {
    super(
      "No credentials provided. Include either " +
      "'X-ANIP-Token: <anip-token>' or " +
      "'X-ANIP-API-Key: <key>' header."
    );
    this.name = "CredentialError";
  }
}

export class IssuanceError extends Error {
  readonly error: string;
  constructor(error: string) {
    super(`Token issuance denied: ${error}`);
    this.name = "IssuanceError";
    this.error = error;
  }
}

export class ANIPInvoker {
  private service: ANIPService;

  constructor(service: ANIPService) {
    this.service = service;
  }

  async invoke(
    capabilityName: string,
    args: Record<string, unknown>,
    opts: { token?: string; apiKey?: string },
  ): Promise<Record<string, unknown>> {
    if (opts.token) {
      return this.invokeWithToken(capabilityName, args, opts.token);
    } else if (opts.apiKey) {
      return this.invokeWithApiKey(capabilityName, args, opts.apiKey);
    } else {
      throw new CredentialError();
    }
  }

  private async invokeWithToken(
    capabilityName: string,
    args: Record<string, unknown>,
    token: string,
  ): Promise<Record<string, unknown>> {
    const invokeUrl = this.service.endpoints.invoke.replace(
      "{capability}",
      capabilityName,
    );
    const resp = await fetch(invokeUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, parameters: args }),
    });
    if (!resp.ok) {
      throw new Error(`Invocation failed: ${resp.status}`);
    }
    return (await resp.json()) as Record<string, unknown>;
  }

  private async invokeWithApiKey(
    capabilityName: string,
    args: Record<string, unknown>,
    apiKey: string,
  ): Promise<Record<string, unknown>> {
    const capability = this.service.capabilities.get(capabilityName);
    let capScope = ["*"];
    if (capability && capability.minimumScope.length > 0) {
      capScope = capability.minimumScope;
    }

    // Step 1: Request a signed token
    const tokenResp = await fetch(this.service.endpoints.tokens, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        subject: "adapter:anip-rest-adapter-ts",
        scope: capScope,
        capability: capabilityName,
      }),
    });
    if (!tokenResp.ok) {
      throw new Error(`Token request failed: ${tokenResp.status}`);
    }
    const tokenData = (await tokenResp.json()) as Record<string, unknown>;
    if (!tokenData.issued) {
      throw new IssuanceError(
        (tokenData.error as string) ?? "unknown error",
      );
    }
    const jwt = tokenData.token as string;

    // Step 2: Invoke with the signed token
    return this.invokeWithToken(capabilityName, args, jwt);
  }
}
