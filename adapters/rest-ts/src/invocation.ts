/**
 * ANIP capability invocation from REST requests.
 *
 * Handles delegation token construction and ANIP invocation,
 * returning raw dicts for JSON serialization (NOT translated
 * strings like the MCP adapter).
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
    this.rootTokenId = `rest-adapter-${randomHex(12)}`;
    const expires = new Date(
      Date.now() + this.config.tokenTtlMinutes * 60 * 1000
    ).toISOString();

    const rootToken = {
      token_id: this.rootTokenId,
      issuer: this.config.issuer,
      subject: "adapter:anip-rest-adapter-ts",
      scope: this.config.scope,
      purpose: {
        capability: "*",
        parameters: {},
        task_id: `rest-session-${randomHex(8)}`,
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
  ): Promise<Record<string, unknown>> {
    const capTokenId = `rest-${capabilityName}-${randomHex(8)}`;
    const expires = new Date(
      Date.now() + this.config.tokenTtlMinutes * 60 * 1000
    ).toISOString();

    // Determine scope for this capability
    const capability = this.service.capabilities.get(capabilityName);
    let capScope = this.config.scope;
    if (capability && capability.minimumScope.length > 0) {
      if (this.config.scope.includes("*")) {
        // Wildcard scope — use the capability's required scopes directly
        capScope = capability.minimumScope;
      } else {
        // Narrow scope to what the capability needs
        const needed = capability.minimumScope;
        const narrowed = this.config.scope.filter((s) => {
          const base = s.split(":")[0];
          return needed.includes(base) || needed.includes(s);
        });
        if (narrowed.length > 0) {
          capScope = narrowed;
        }
      }
    }

    const capToken = {
      token_id: capTokenId,
      issuer: "adapter:anip-rest-adapter-ts",
      subject: "adapter:anip-rest-adapter-ts",
      scope: capScope,
      purpose: {
        capability: capabilityName,
        parameters: args,
        task_id: `rest-invoke-${randomHex(8)}`,
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

    return (await invokeResp.json()) as Record<string, unknown>;
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
