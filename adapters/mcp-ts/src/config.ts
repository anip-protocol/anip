/**
 * Bridge configuration — from environment variables or defaults.
 */

export interface BridgeConfig {
  anipServiceUrl: string;
  scope: string[];
  enrichDescriptions: boolean;
  apiKey: string;
}

export function loadConfig(): BridgeConfig {
  return {
    anipServiceUrl:
      process.env.ANIP_SERVICE_URL ?? "http://localhost:8000",
    scope: (process.env.ANIP_SCOPE ?? "*").split(","),
    enrichDescriptions: process.env.ANIP_ENRICH !== "false",
    apiKey: process.env.ANIP_API_KEY ?? "demo-human-key",
  };
}
