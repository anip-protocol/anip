/**
 * ANIP capability invocation from MCP tool calls.
 *
 * Handles delegation token construction and ANIP invocation,
 * translating ANIP responses back into MCP-compatible results.
 */

import type { ANIPService } from "./discovery.js";

interface DelegationConfig {
  issuer: string;
  scope: string[];
  tokenTtlMinutes: number;
}

export class ANIPInvoker {
  private service: ANIPService;
  private config: DelegationConfig;
  private rootTokenId: string | null = null;

  constructor(service: ANIPService, config: DelegationConfig) {
    this.service = service;
    this.config = config;
  }

  async setup(): Promise<void> {
    this.rootTokenId = `mcp-bridge-${randomHex(12)}`;
    const expires = new Date(
      Date.now() + this.config.tokenTtlMinutes * 60 * 1000
    ).toISOString();

    const rootToken = {
      token_id: this.rootTokenId,
      issuer: this.config.issuer,
      subject: "bridge:anip-mcp-bridge-ts",
      scope: this.config.scope,
      purpose: {
        capability: "*",
        parameters: {},
        task_id: `mcp-session-${randomHex(8)}`,
      },
      parent: null,
      expires,
      constraints: {
        max_delegation_depth: 2,
        concurrent_branches: "allowed",
      },
    };

    const resp = await fetch(this.service.endpoints.tokens, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rootToken),
    });
    if (!resp.ok) {
      throw new Error(`Token registration failed: ${resp.status}`);
    }
  }

  async invoke(
    capabilityName: string,
    args: Record<string, unknown>
  ): Promise<string> {
    const capTokenId = `mcp-${capabilityName}-${randomHex(8)}`;
    const expires = new Date(
      Date.now() + this.config.tokenTtlMinutes * 60 * 1000
    ).toISOString();

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

    const capToken = {
      token_id: capTokenId,
      issuer: "bridge:anip-mcp-bridge-ts",
      subject: "bridge:anip-mcp-bridge-ts",
      scope: capScope,
      purpose: {
        capability: capabilityName,
        parameters: args,
        task_id: `mcp-invoke-${randomHex(8)}`,
      },
      parent: this.rootTokenId,
      expires,
      constraints: {
        max_delegation_depth: 2,
        concurrent_branches: "allowed",
      },
    };

    // Register the capability token
    const tokenResp = await fetch(this.service.endpoints.tokens, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(capToken),
    });
    if (!tokenResp.ok) {
      throw new Error(`Token registration failed: ${tokenResp.status}`);
    }

    // Invoke the capability
    const invokeUrl = this.service.endpoints.invoke.replace(
      "{capability}",
      capabilityName
    );
    const invokeResp = await fetch(invokeUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        delegation_token: capToken,
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

function randomHex(length: number): string {
  const chars = "0123456789abcdef";
  let result = "";
  for (let i = 0; i < length; i++) {
    result += chars[Math.floor(Math.random() * 16)];
  }
  return result;
}
