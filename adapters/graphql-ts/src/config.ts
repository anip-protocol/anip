/**
 * Adapter configuration — from YAML file, environment variables, or defaults.
 */

import { readFileSync, existsSync } from "node:fs";
import { parse as parseYaml } from "yaml";

export interface DelegationConfig {
  issuer: string;
  scope: string[];
  tokenTtlMinutes: number;
}

export interface AdapterConfig {
  anipServiceUrl: string;
  port: number;
  delegation: DelegationConfig;
  graphqlPath: string;
}

export function loadConfig(configPath?: string): AdapterConfig {
  // Find config file: explicit path > env var > ./adapter.yaml > defaults
  let path = configPath ?? process.env.ANIP_ADAPTER_CONFIG;
  if (path && !existsSync(path)) {
    path = undefined;
  }
  if (!path && existsSync("adapter.yaml")) {
    path = "adapter.yaml";
  }

  if (!path) {
    // Use environment variables or defaults
    return {
      anipServiceUrl:
        process.env.ANIP_SERVICE_URL ?? "http://localhost:8000",
      port: Number(process.env.ANIP_ADAPTER_PORT ?? "3002"),
      delegation: {
        issuer: process.env.ANIP_ISSUER ?? "human:user@example.com",
        scope: (process.env.ANIP_SCOPE ?? "*").split(","),
        tokenTtlMinutes: Number(process.env.ANIP_TOKEN_TTL ?? "60"),
      },
      graphqlPath: "/graphql",
    };
  }

  // Load from YAML
  const raw = readFileSync(path, "utf-8");
  const data = parseYaml(raw) as Record<string, unknown>;

  const delegationData = (data.delegation ?? {}) as Record<string, unknown>;
  const delegation: DelegationConfig = {
    issuer: (delegationData.issuer as string) ?? "human:user@example.com",
    scope: (delegationData.scope as string[]) ?? ["*"],
    tokenTtlMinutes: Number(delegationData.token_ttl_minutes ?? 60),
  };

  const graphqlData = (data.graphql ?? {}) as Record<string, unknown>;

  return {
    anipServiceUrl:
      (data.anip_service_url as string) ?? "http://localhost:8000",
    port: Number(data.port ?? 3002),
    delegation,
    graphqlPath: (graphqlData.path as string) ?? "/graphql",
  };
}
