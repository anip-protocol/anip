/**
 * Adapter configuration — from YAML file, environment variables, or defaults.
 */

import { readFileSync, existsSync } from "node:fs";
import { parse as parseYaml } from "yaml";

export interface AdapterConfig {
  anipServiceUrl: string;
  port: number;
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
      graphqlPath: "/graphql",
    };
  }

  // Load from YAML
  const raw = readFileSync(path, "utf-8");
  const data = parseYaml(raw) as Record<string, unknown>;

  const graphqlData = (data.graphql ?? {}) as Record<string, unknown>;

  return {
    anipServiceUrl:
      (data.anip_service_url as string) ?? "http://localhost:8000",
    port: Number(data.port ?? 3002),
    graphqlPath: (graphqlData.path as string) ?? "/graphql",
  };
}
