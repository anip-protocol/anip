/**
 * ANIP service discovery and manifest fetching.
 */

export interface ANIPCapability {
  name: string;
  description: string;
  sideEffect: string;
  rollbackWindow: string | null;
  minimumScope: string[];
  financial: boolean;
  contractVersion: string;
  inputs: Array<{
    name: string;
    type: string;
    required?: boolean;
    default?: unknown;
    description?: string;
  }>;
  output: { type: string; fields: string[] };
  cost: Record<string, unknown> | null;
  requires: Array<{ capability: string; reason: string }>;
}

export interface ANIPService {
  baseUrl: string;
  protocol: string;
  compliance: string;
  endpoints: Record<string, string>;
  capabilities: Map<string, ANIPCapability>;
}

export async function discoverService(anipUrl: string): Promise<ANIPService> {
  // Step 1: Fetch discovery document
  const discoveryUrl = `${anipUrl.replace(/\/$/, "")}/.well-known/anip`;
  const discoveryResp = await fetch(discoveryUrl);
  if (!discoveryResp.ok) {
    throw new Error(
      `Discovery failed: ${discoveryResp.status} ${discoveryResp.statusText}`
    );
  }
  const { anip_discovery: discovery } = (await discoveryResp.json()) as {
    anip_discovery: Record<string, unknown>;
  };

  const baseUrl = discovery.base_url as string;
  const endpoints = discovery.endpoints as Record<string, string>;

  // Step 2: Fetch full manifest
  const manifestUrl = resolveUrl(baseUrl, endpoints.manifest);
  const manifestResp = await fetch(manifestUrl);
  if (!manifestResp.ok) {
    throw new Error(
      `Manifest fetch failed: ${manifestResp.status} ${manifestResp.statusText}`
    );
  }
  const manifest = (await manifestResp.json()) as {
    capabilities: Record<string, Record<string, unknown>>;
  };

  // Step 3: Build capability objects
  const capabilities = new Map<string, ANIPCapability>();
  for (const [name, cap] of Object.entries(manifest.capabilities)) {
    const sideEffect = cap.side_effect as { type: string; rollback_window?: string };
    const minimumScope = cap.minimum_scope as string[];
    capabilities.set(name, {
      name,
      description: cap.description as string,
      sideEffect: sideEffect.type,
      rollbackWindow: sideEffect.rollback_window ?? null,
      minimumScope: minimumScope,
      financial: (cap.cost as Record<string, unknown>)?.financial != null,
      contractVersion: (cap.contract_version as string) ?? "1.0",
      inputs: (cap.inputs as ANIPCapability["inputs"]) ?? [],
      output: (cap.output as ANIPCapability["output"]) ?? {
        type: "unknown",
        fields: [],
      },
      cost: (cap.cost as Record<string, unknown>) ?? null,
      requires:
        (cap.requires as Array<{ capability: string; reason: string }>) ?? [],
    });
  }

  // Resolve all endpoint URLs
  const resolvedEndpoints: Record<string, string> = {};
  for (const [k, v] of Object.entries(endpoints)) {
    resolvedEndpoints[k] = resolveUrl(baseUrl, v);
  }

  return {
    baseUrl,
    protocol: discovery.protocol as string,
    compliance: (discovery.compliance as string) ?? "anip-compliant",
    endpoints: resolvedEndpoints,
    capabilities,
  };
}

function resolveUrl(baseUrl: string, path: string): string {
  if (path.startsWith("http")) return path;
  return `${baseUrl.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}
