/**
 * Bridge configuration — from environment variables or defaults.
 */

export interface BridgeConfig {
  anipServiceUrl: string;
  issuer: string;
  scope: string[];
  tokenTtlMinutes: number;
  enrichDescriptions: boolean;
}

export function loadConfig(): BridgeConfig {
  return {
    anipServiceUrl:
      process.env.ANIP_SERVICE_URL ?? "http://localhost:8000",
    issuer:
      process.env.ANIP_ISSUER ?? "human:user@example.com",
    scope: (process.env.ANIP_SCOPE ?? "*").split(","),
    tokenTtlMinutes: Number(process.env.ANIP_TOKEN_TTL ?? "60"),
    enrichDescriptions: process.env.ANIP_ENRICH !== "false",
  };
}
