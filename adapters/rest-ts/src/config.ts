/**
 * Adapter configuration — from YAML file, environment variables, or defaults.
 */

import { readFileSync, existsSync } from "node:fs";
import { parse as parseYaml } from "yaml";

export interface RouteOverride {
  path: string;
  method: string;
}

export interface AdapterConfig {
  anipServiceUrl: string;
  port: number;
  routes: Record<string, RouteOverride>;
}

export function loadConfig(configPath?: string): AdapterConfig {
  let path = configPath ?? process.env.ANIP_ADAPTER_CONFIG;
  if (path && !existsSync(path)) {
    path = undefined;
  }
  if (!path && existsSync("adapter.yaml")) {
    path = "adapter.yaml";
  }

  if (!path) {
    return {
      anipServiceUrl:
        process.env.ANIP_SERVICE_URL ?? "http://localhost:8000",
      port: Number(process.env.ANIP_ADAPTER_PORT ?? "3001"),
      routes: {},
    };
  }

  const raw = readFileSync(path, "utf-8");
  const data = parseYaml(raw) as Record<string, unknown>;

  const routes: Record<string, RouteOverride> = {};
  const routesData = (data.routes ?? {}) as Record<
    string,
    Record<string, string>
  >;
  for (const [capName, routeData] of Object.entries(routesData)) {
    routes[capName] = {
      path: routeData.path,
      method: (routeData.method ?? "POST").toUpperCase(),
    };
  }

  return {
    anipServiceUrl:
      (data.anip_service_url as string) ?? "http://localhost:8000",
    port: Number(data.port ?? 3001),
    routes,
  };
}
