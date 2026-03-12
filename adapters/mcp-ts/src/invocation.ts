/**
 * ANIP capability invocation from MCP tool calls.
 *
 * Handles delegation token construction and ANIP invocation,
 * translating ANIP responses back into MCP-compatible results.
 */

import type { ANIPService } from "./discovery.js";

interface DelegationConfig {
  scope: string[];
  apiKey: string;
}

export class ANIPInvoker {
  private service: ANIPService;
  private config: DelegationConfig;
  constructor(service: ANIPService, config: DelegationConfig) {
    this.service = service;
    this.config = config;
  }

  async setup(): Promise<void> {
    // v0.2: tokens are requested per-invocation, no root token needed
  }

  async invoke(
    capabilityName: string,
    args: Record<string, unknown>
  ): Promise<string> {
    // Narrow scope to what the capability needs
    const capability = this.service.capabilities.get(capabilityName);
    let capScope = this.config.scope;
    if (capability) {
      const needed = new Set(capability.minimumScope);
      const narrowed = this.config.scope.filter((s) => {
        const base = s.split(":")[0];
        return needed.has(base) || needed.has(s);
      });
      if (narrowed.length > 0) {
        capScope = narrowed;
      }
    }

    // Step 1: Request a signed JWT token
    const tokenResp = await fetch(this.service.endpoints.tokens, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${this.config.apiKey}`,
      },
      body: JSON.stringify({
        subject: "bridge:anip-mcp-bridge-ts",
        scope: capScope,
        capability: capabilityName,
      }),
    });
    if (!tokenResp.ok) {
      throw new Error(`Token request failed: ${tokenResp.status}`);
    }
    const tokenData = (await tokenResp.json()) as Record<string, unknown>;
    if (!tokenData.issued) {
      const error = (tokenData.error as string) ?? "unknown error";
      return `FAILED: token_issuance\nDetail: ${error}\nRetryable: no`;
    }
    const jwt = tokenData.token as string;

    // Step 2: Invoke with the JWT
    const invokeUrl = this.service.endpoints.invoke.replace(
      "{capability}",
      capabilityName
    );
    const invokeResp = await fetch(invokeUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token: jwt,
        parameters: args,
      }),
    });
    if (!invokeResp.ok) {
      throw new Error(`Invocation failed: ${invokeResp.status}`);
    }

    const result = (await invokeResp.json()) as Record<string, unknown>;
    return this.translateResponse(result);
  }

  private translateResponse(response: Record<string, unknown>): string {
    if (response.success) {
      const result = response.result as Record<string, unknown>;
      const parts = [JSON.stringify(result, null, 2)];

      const costActual = response.cost_actual as Record<string, unknown> | undefined;
      if (costActual) {
        const financial = costActual.financial as Record<string, unknown>;
        const amount = financial?.amount;
        const currency = (financial?.currency as string) ?? "USD";
        if (amount !== undefined) {
          parts.push(`\n[Cost: ${currency} ${amount}]`);
        }
        const variance = costActual.variance_from_estimate as string | undefined;
        if (variance) {
          parts.push(`[Variance from estimate: ${variance}]`);
        }
      }

      return parts.join("");
    }

    // Failure
    const failure = response.failure as Record<string, unknown>;
    const parts = [
      `FAILED: ${failure?.type ?? "unknown"}`,
      `Detail: ${failure?.detail ?? "no detail"}`,
    ];

    const resolution = failure?.resolution as Record<string, unknown> | undefined;
    if (resolution) {
      parts.push(`Resolution: ${resolution.action ?? ""}`);
      if (resolution.requires) {
        parts.push(`Requires: ${resolution.requires}`);
      }
      if (resolution.grantable_by) {
        parts.push(`Grantable by: ${resolution.grantable_by}`);
      }
    }

    const retry = failure?.retry as boolean;
    parts.push(`Retryable: ${retry ? "yes" : "no"}`);

    return parts.join("\n");
  }
}
