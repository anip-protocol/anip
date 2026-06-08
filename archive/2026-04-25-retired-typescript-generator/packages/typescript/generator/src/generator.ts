import { mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type {
  AnipServiceDefinition,
  BuildTypeScriptProjectOptions,
  CapabilityFormalization,
  CapabilityInputFormalization,
  GenerateTypeScriptProjectOptions,
  GeneratedTypeScriptProject,
  IntegrationBackendBinding,
  IntegrationCapabilityMapping,
  ServiceTopologyBinding,
} from "./types.js";

const ANIP_PACKAGE_VERSION = "0.22.0";
const DEFAULT_PORT = 4100;
const GENERATOR_DIR = path.dirname(fileURLToPath(import.meta.url));
const TYPESCRIPT_PACKAGES_DIR = path.resolve(GENERATOR_DIR, "..", "..");

function localDependencyPath(...segments: string[]): string {
  return `file:${path.join(TYPESCRIPT_PACKAGES_DIR, ...segments)}`;
}

interface GeneratedCapabilityRuntimeMetadata {
  service_id: string;
  service_name: string;
  capability_id: string;
  title: string;
  summary: string;
  intent_type: string;
  operation_type: string;
  execution_posture: string;
  side_effect_level: string;
  backend_operation: string;
  path_template: string;
  output_shape: string;
  subject_kind: string;
  context_type: string;
  output_intent: string;
  minimum_scope: string[];
  required_inputs: CapabilityInputFormalization[];
  optional_inputs: CapabilityInputFormalization[];
  sample_parameters: Record<string, unknown>;
  backend_input_mode: "implicit" | "hybrid" | "explicit";
  derived_required_backend_inputs: string[];
  derived_optional_backend_inputs: string[];
  explicit_required_backend_inputs: string[];
  explicit_optional_backend_inputs: string[];
  backend_bindings: IntegrationBackendBinding[];
  governance: {
    approval_rule_refs: string[];
    denial_rule_refs: string[];
    clarification_rule_refs: string[];
    audit_required: boolean;
  };
  outbound_controls: unknown;
}

export async function readServiceDefinition(definitionPath: string): Promise<AnipServiceDefinition> {
  const raw = await readFile(definitionPath, "utf8");
  return JSON.parse(raw) as AnipServiceDefinition;
}

export async function generateTypeScriptProject(
  definition: AnipServiceDefinition,
  options: GenerateTypeScriptProjectOptions,
): Promise<GeneratedTypeScriptProject> {
  const built = buildTypeScriptProject(definition, {
    dependencySource: options.dependencySource ?? "registry",
    httpRuntime: options.httpRuntime ?? "hono",
    packageName: options.packageName,
    port: options.port ?? DEFAULT_PORT,
  });
  await writeGeneratedProject(built, options.outputDir, { force: options.force ?? false });
  return built;
}

export function buildTypeScriptProject(
  definition: AnipServiceDefinition,
  options: BuildTypeScriptProjectOptions,
): GeneratedTypeScriptProject {
  assertDefinition(definition);
  const systemName = definition.identity?.system_name?.trim() || "generated-anip-service";
  const packageName = options.packageName?.trim() || systemNameToPackageName(systemName);
  const services = buildServiceMetadata(definition);
  const capabilities = buildCapabilityMetadata(definition, services);
  if (capabilities.length === 0) {
    throw new Error("Service Definition must include at least one capability formalization.");
  }

  const runtimeTarget = {
    system_name: systemName,
    domain_name: definition.identity?.domain_name?.trim() || "unspecified",
    delivery_model: definition.identity?.delivery_model?.trim() || "service_platform",
    architecture_shape: definition.identity?.architecture_shape?.trim() || "single_service",
    protocols: uniqueStrings(definition.generation?.protocols ?? ["https"]),
    services,
    authority: {
      approval_expectation: definition.authority?.approval_expectation ?? "project_specific",
      blocked_failure_posture: definition.authority?.blocked_failure_posture ?? "clarify_or_stop",
    },
    audit: {
      durable_records_required: Boolean(definition.audit?.durable_records_required),
      searchable_history_required: Boolean(definition.audit?.searchable_history_required),
    },
  };

  const definitionJson = JSON.stringify(definition, null, 2);
  const runtimeTargetJson = JSON.stringify(runtimeTarget, null, 2);
  const capabilityMetadataJson = JSON.stringify(capabilities, null, 2);

  return {
    packageName,
    systemName,
    files: [
      { path: "package.json", content: buildGeneratedPackageJson(packageName, options.dependencySource) },
      { path: "tsconfig.json", content: buildGeneratedTsconfig() },
      { path: "vitest.config.ts", content: buildGeneratedVitestConfig() },
      { path: "README.md", content: buildGeneratedReadme(systemName) },
      { path: "anip-service-definition.json", content: `${definitionJson}\n` },
      { path: "src/generated/service-definition.ts", content: buildGeneratedServiceDefinitionModule(definitionJson) },
      { path: "src/generated/runtime-target.ts", content: buildGeneratedRuntimeTargetModule(runtimeTargetJson, capabilityMetadataJson) },
      { path: "src/generated/capabilities.ts", content: buildGeneratedCapabilitiesModule() },
      { path: "src/runtime/backend-adapter.ts", content: buildGeneratedBackendAdapterModule() },
      { path: "src/runtime/policy.ts", content: buildGeneratedPolicyModule() },
      { path: "src/app.ts", content: buildGeneratedAppModule() },
      { path: "src/main.ts", content: buildGeneratedMainModule(options.port, systemName) },
      { path: "tests/service-smoke.test.ts", content: buildGeneratedSmokeTestModule() },
    ],
  };
}

export async function writeGeneratedProject(
  project: GeneratedTypeScriptProject,
  outputDir: string,
  options: { force: boolean },
): Promise<void> {
  const outputPath = path.resolve(outputDir);
  if (options.force) {
    await rm(outputPath, { recursive: true, force: true });
  } else {
    try {
      await stat(outputPath);
      throw new Error(`Output directory already exists: ${outputPath}`);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
  }

  await mkdir(outputPath, { recursive: true });
  for (const file of project.files) {
    const destination = path.join(outputPath, file.path);
    await mkdir(path.dirname(destination), { recursive: true });
    await writeFile(destination, file.content, "utf8");
  }
}

function assertDefinition(definition: AnipServiceDefinition): void {
  if (!definition.identity?.system_name?.trim()) {
    throw new Error("Service Definition is missing identity.system_name.");
  }
  if (!Array.isArray(definition.capability_formalizations) || definition.capability_formalizations.length === 0) {
    throw new Error("Service Definition must include capability_formalizations.");
  }
}

function buildServiceMetadata(definition: AnipServiceDefinition) {
  const topologyById = new Map<string, ServiceTopologyBinding>();
  for (const binding of definition.service_topology_bindings ?? []) {
    topologyById.set(binding.service_id, binding);
  }

  const serviceIds = new Set<string>();
  for (const capability of definition.capability_formalizations ?? []) {
    if (capability.service_id?.trim()) serviceIds.add(capability.service_id.trim());
  }
  for (const serviceId of definition.generation?.selected_service_ids ?? []) {
    if (typeof serviceId === "string" && serviceId.trim()) serviceIds.add(serviceId.trim());
  }

  return Array.from(serviceIds).map((serviceId) => {
    const topology = topologyById.get(serviceId);
    return {
      service_id: serviceId,
      service_name: topology?.service_name?.trim() || titleCase(serviceId.replace(/[-_]+/g, " ")),
      source_role: topology?.source_role?.trim() || "application_integration",
      source_capabilities: topology?.source_capabilities ?? [],
      formalized_capability_ids: topology?.formalized_capability_ids ?? [],
      owned_concept_ids: topology?.owned_concept_ids ?? [],
    };
  });
}

function buildCapabilityMetadata(
  definition: AnipServiceDefinition,
  services: Array<ReturnType<typeof buildServiceMetadata>[number]>,
): GeneratedCapabilityRuntimeMetadata[] {
  const serviceNameById = new Map(services.map((service) => [service.service_id, service.service_name]));
  const mappingByCapability = new Map<string, IntegrationCapabilityMapping>();
  for (const mapping of definition.integration_fronting?.capability_mappings ?? []) {
    mappingByCapability.set(mapping.capability_id, mapping);
  }

  return (definition.capability_formalizations ?? []).map((capability) => {
    const mapping = mappingByCapability.get(capability.capability_id);
    const requiredInputs = capability.inputs.filter((input) => input.required);
    const optionalInputs = capability.inputs.filter((input) => !input.required);
    return {
      service_id: capability.service_id,
      service_name: serviceNameById.get(capability.service_id) ?? titleCase(capability.service_id.replace(/[-_]+/g, " ")),
      capability_id: capability.capability_id,
      title: capability.title,
      summary: capability.summary,
      intent_type: capability.intent_type,
      operation_type: capability.operation_type,
      execution_posture: mapping?.execution_posture ?? capability.intent_type,
      side_effect_level: capability.side_effect_level,
      backend_operation: capability.backend_operation,
      path_template: capability.path_template,
      output_shape: capability.output_shape,
      subject_kind: mapping?.subject_kind?.trim() || capability.subject_kind?.trim() || "record",
      context_type: mapping?.context_type?.trim() || capability.context_type?.trim() || "governed_request",
      output_intent: mapping?.output_intent?.trim() || capability.output_intent?.trim() || capability.output_shape || "governed_result",
      minimum_scope: [capability.capability_id],
      required_inputs: requiredInputs,
      optional_inputs: optionalInputs,
      sample_parameters: buildSampleParameters(capability.inputs),
      backend_input_mode: mapping?.backend_input_mode ?? "implicit",
      derived_required_backend_inputs: uniqueStrings(mapping?.derived_required_backend_inputs ?? []),
      derived_optional_backend_inputs: uniqueStrings(mapping?.derived_optional_backend_inputs ?? []),
      explicit_required_backend_inputs: uniqueStrings(mapping?.explicit_required_backend_inputs ?? []),
      explicit_optional_backend_inputs: uniqueStrings(mapping?.explicit_optional_backend_inputs ?? []),
      backend_bindings: normalizeBackendBindings(mapping),
      governance: {
        approval_rule_refs: uniqueStrings(mapping?.approval_rule_refs ?? []),
        denial_rule_refs: uniqueStrings(mapping?.denial_rule_refs ?? []),
        clarification_rule_refs: uniqueStrings(mapping?.clarification_rule_refs ?? []),
        audit_required: Boolean(mapping?.audit_required),
      },
      outbound_controls: mapping?.outbound_controls ?? {},
    };
  });
}

function normalizeBackendBindings(mapping: IntegrationCapabilityMapping | undefined): IntegrationBackendBinding[] {
  if (!mapping) return [];
  if (Array.isArray(mapping.backend_bindings) && mapping.backend_bindings.length > 0) {
    return mapping.backend_bindings.map((binding) => ({
      backend_kind: binding.backend_kind,
      connection_ref: binding.connection_ref,
      raw_operation_refs: binding.raw_operation_refs ?? [],
      backend_input_mode: binding.backend_input_mode ?? mapping.backend_input_mode ?? "implicit",
      derived_required_backend_inputs: uniqueStrings(binding.derived_required_backend_inputs ?? mapping.derived_required_backend_inputs ?? []),
      derived_optional_backend_inputs: uniqueStrings(binding.derived_optional_backend_inputs ?? mapping.derived_optional_backend_inputs ?? []),
      explicit_required_backend_inputs: uniqueStrings(binding.explicit_required_backend_inputs ?? mapping.explicit_required_backend_inputs ?? []),
      explicit_optional_backend_inputs: uniqueStrings(binding.explicit_optional_backend_inputs ?? mapping.explicit_optional_backend_inputs ?? []),
      matched_discovery_record_ids: binding.matched_discovery_record_ids ?? [],
      status: binding.status ?? "ready",
      status_detail: binding.status_detail ?? "",
    }));
  }

  return [
    {
      backend_kind: mapping.backend_kind,
      connection_ref: mapping.connection_ref,
      raw_operation_refs: mapping.raw_operation_refs ?? [],
      backend_input_mode: mapping.backend_input_mode ?? "implicit",
      derived_required_backend_inputs: uniqueStrings(mapping.derived_required_backend_inputs ?? []),
      derived_optional_backend_inputs: uniqueStrings(mapping.derived_optional_backend_inputs ?? []),
      explicit_required_backend_inputs: uniqueStrings(mapping.explicit_required_backend_inputs ?? []),
      explicit_optional_backend_inputs: uniqueStrings(mapping.explicit_optional_backend_inputs ?? []),
      matched_discovery_record_ids: [],
      status: "ready",
      status_detail: "",
    },
  ];
}

function buildSampleParameters(inputs: CapabilityInputFormalization[]): Record<string, unknown> {
  return Object.fromEntries(inputs.map((input) => [input.input_name, sampleValueForInput(input)]));
}

function sampleValueForInput(input: CapabilityInputFormalization): unknown {
  if (input.allowed_values?.length) return input.allowed_values[0];
  if (input.default_value?.trim()) {
    const trimmed = input.default_value.trim();
    if (trimmed === "true") return true;
    if (trimmed === "false") return false;
    if (!Number.isNaN(Number(trimmed)) && trimmed !== "") return Number(trimmed);
    return trimmed;
  }

  const inputType = input.input_type.toLowerCase();
  if (inputType.includes("bool")) return false;
  if (inputType.includes("int") || inputType.includes("number") || inputType.includes("float")) return 1;
  if (inputType.includes("array") || inputType.endsWith("[]")) return [];
  if (inputType.includes("object") || inputType.includes("json")) return {};
  return `${input.input_name}-value`;
}

function buildGeneratedPackageJson(packageName: string, dependencySource: "registry" | "local"): string {
  const dependencySpecs = dependencySource === "local"
    ? {
        "@anip-dev/core": localDependencyPath("core"),
        "@anip-dev/crypto": localDependencyPath("crypto"),
        "@anip-dev/server": localDependencyPath("server"),
        "@anip-dev/service": localDependencyPath("service"),
        "@anip-dev/hono": localDependencyPath("hono"),
        hono: localDependencyPath("node_modules", "hono"),
        "@hono/node-server": localDependencyPath("node_modules", "@hono", "node-server"),
      }
    : {
        "@anip-dev/hono": ANIP_PACKAGE_VERSION,
        "@anip-dev/service": ANIP_PACKAGE_VERSION,
        "@hono/node-server": "^1.11.0",
        hono: "^4.12.8",
      };

  return `${JSON.stringify(
    {
      name: packageName,
      private: true,
      version: "0.1.0",
      type: "module",
      scripts: {
        dev: "tsx src/main.ts",
        build: "tsc -p tsconfig.json",
        start: "node dist/main.js",
        test: "vitest run",
      },
      dependencies: dependencySpecs,
      devDependencies: {
        "@types/node": "^22.0.0",
        tsx: "^4.20.6",
        typescript: "^5.5.0",
        vitest: "^4.1.0",
      },
    },
    null,
    2,
  )}\n`;
}

function buildGeneratedTsconfig(): string {
  return `${JSON.stringify(
    {
      compilerOptions: {
        target: "ES2022",
        module: "Node16",
        moduleResolution: "Node16",
        declaration: true,
        sourceMap: true,
        strict: true,
        esModuleInterop: true,
        skipLibCheck: true,
        outDir: "dist",
        rootDir: "src",
      },
      include: ["src"],
    },
    null,
    2,
  )}\n`;
}

function buildGeneratedVitestConfig(): string {
  return [
    'import { defineConfig } from "vitest/config";',
    "",
    "export default defineConfig({",
    "  test: {",
    '    include: ["tests/**/*.test.ts"],',
    "  },",
    "});",
    "",
  ].join("\n");
}

function buildGeneratedReadme(systemName: string): string {
  return [
    `# ${titleCase(systemName.replace(/[-_]+/g, " "))}`,
    "",
    "Generated by `@anip-dev/generator-typescript` from an exported `anip-service-definition.json`.",
    "",
    "## What is generated",
    "",
    "- generic ANIP HTTP host using `@anip-dev/service` and `@anip-dev/hono`",
    "- generated capability declarations and invoke routing",
    "- generated smoke tests",
    "- explicit backend adapter and policy seams for handwritten completion",
    "",
    "## Extension seams",
    "",
    "- `src/runtime/backend-adapter.ts` owns provider-specific backend execution",
    "- `src/runtime/policy.ts` owns policy decisions that cannot remain declarative",
    "",
    "## Commands",
    "",
    "- `npm run dev`",
    "- `npm run build`",
    "- `npm test`",
    "",
  ].join("\n");
}

function buildGeneratedServiceDefinitionModule(definitionJson: string): string {
  return [
    "// Generated from an exported ANIP Service Definition.",
    `export const serviceDefinition = ${definitionJson} as const;`,
    "",
  ].join("\n");
}

function buildGeneratedRuntimeTargetModule(runtimeTargetJson: string, capabilityMetadataJson: string): string {
  return [
    "// Generated runtime target metadata.",
    "",
    "export type GeneratedBackendBinding = {",
    "  backend_kind: string;",
    "  connection_ref: string;",
    "  raw_operation_refs: string[];",
    '  backend_input_mode?: "implicit" | "hybrid" | "explicit";',
    "  derived_required_backend_inputs?: string[];",
    "  derived_optional_backend_inputs?: string[];",
    "  explicit_required_backend_inputs?: string[];",
    "  explicit_optional_backend_inputs?: string[];",
    "  matched_discovery_record_ids?: string[];",
    "  status?: string;",
    "  status_detail?: string;",
    "};",
    "",
    "export type GeneratedCapabilityInputMetadata = {",
    "  input_name: string;",
    "  input_type: string;",
    "  required: boolean;",
    "  summary: string;",
    "  default_value: string;",
    "  allowed_values: string[];",
    "  [key: string]: unknown;",
    "};",
    "",
    "export type GeneratedCapabilityRuntimeMetadata = {",
    "  service_id: string;",
    "  service_name: string;",
    "  capability_id: string;",
    "  title: string;",
    "  summary: string;",
    "  intent_type: string;",
    "  operation_type: string;",
    "  execution_posture: string;",
    "  side_effect_level: string;",
    "  backend_operation: string;",
    "  path_template: string;",
    "  output_shape: string;",
    "  subject_kind: string;",
    "  context_type: string;",
    "  output_intent: string;",
    "  minimum_scope: string[];",
    "  required_inputs: GeneratedCapabilityInputMetadata[];",
    "  optional_inputs: GeneratedCapabilityInputMetadata[];",
    "  sample_parameters: Record<string, unknown>;",
    '  backend_input_mode: "implicit" | "hybrid" | "explicit";',
    "  derived_required_backend_inputs: string[];",
    "  derived_optional_backend_inputs: string[];",
    "  explicit_required_backend_inputs: string[];",
    "  explicit_optional_backend_inputs: string[];",
    "  backend_bindings: GeneratedBackendBinding[];",
    "  governance: {",
    "    approval_rule_refs: string[];",
    "    denial_rule_refs: string[];",
    "    clarification_rule_refs: string[];",
    "    audit_required: boolean;",
    "  };",
    "  outbound_controls: unknown;",
    "};",
    "",
    "export type EffectiveBackendInputContract = {",
    '  mode: "implicit" | "hybrid" | "explicit";',
    "  required: string[];",
    "  optional: string[];",
    "};",
    "",
    "export type BackendInvocationPlan = {",
    "  selected_binding: GeneratedBackendBinding | null;",
    "  semantic_input: Record<string, unknown>;",
    "  backend_input_contract: EffectiveBackendInputContract;",
    "  unresolved_required_backend_inputs: string[];",
    "};",
    "",
    `export const runtimeTarget = ${runtimeTargetJson} as const;`,
    "",
    `export const generatedCapabilityMetadata: GeneratedCapabilityRuntimeMetadata[] = ${capabilityMetadataJson};`,
    "",
  ].join("\n");
}

function buildGeneratedCapabilitiesModule(): string {
  return [
    'import { ANIPError, defineCapability, type CapabilityDef } from "@anip-dev/service";',
    'import { backendAdapter } from "../runtime/backend-adapter.js";',
    'import { evaluatePolicy } from "../runtime/policy.js";',
    'import { generatedCapabilityMetadata, type BackendInvocationPlan, type EffectiveBackendInputContract, type GeneratedBackendBinding, type GeneratedCapabilityRuntimeMetadata } from "./runtime-target.js";',
    "",
    "const activeSelections = readActiveSelections();",
    "",
    'function readActiveSelections(): Record<string, { backend_kind?: string; connection_ref?: string }> {',
    '  const raw = process.env.ANIP_ACTIVE_BACKEND_SELECTIONS_JSON;',
    "  if (!raw) return {};",
    "  try {",
    '    return JSON.parse(raw) as Record<string, { backend_kind?: string; connection_ref?: string }>;',
    "  } catch {",
    "    return {};",
    "  }",
    "}",
    "",
    "function uniqueStrings(values: string[]) {",
    '  return Array.from(new Set(values.filter(Boolean)));',
    "}",
    "",
    "function effectiveBackendInputContract(capability: GeneratedCapabilityRuntimeMetadata, selectedBinding: GeneratedBackendBinding | null): EffectiveBackendInputContract {",
    '  const mode = selectedBinding?.backend_input_mode || capability.backend_input_mode || "implicit";',
    "  const derivedRequired = selectedBinding?.derived_required_backend_inputs?.length ? selectedBinding.derived_required_backend_inputs : capability.derived_required_backend_inputs;",
    "  const derivedOptional = selectedBinding?.derived_optional_backend_inputs?.length ? selectedBinding.derived_optional_backend_inputs : capability.derived_optional_backend_inputs;",
    "  const explicitRequired = selectedBinding?.explicit_required_backend_inputs?.length ? selectedBinding.explicit_required_backend_inputs : capability.explicit_required_backend_inputs;",
    "  const explicitOptional = selectedBinding?.explicit_optional_backend_inputs?.length ? selectedBinding.explicit_optional_backend_inputs : capability.explicit_optional_backend_inputs;",
    '  if (mode === "explicit") {',
    "    const required = uniqueStrings(explicitRequired || []);",
    "    const optional = uniqueStrings((explicitOptional || []).filter((item) => !required.includes(item)));",
    '    return { mode: "explicit", required, optional };',
    "  }",
    '  if (mode === "hybrid") {',
    "    const required = uniqueStrings([...(derivedRequired || []), ...(explicitRequired || [])]);",
    "    const optional = uniqueStrings([...(derivedOptional || []), ...(explicitOptional || [])]).filter((item) => !required.includes(item));",
    '    return { mode: "hybrid", required, optional };',
    "  }",
    "  const required = uniqueStrings(derivedRequired || []);",
    "  const optional = uniqueStrings(derivedOptional || []).filter((item) => !required.includes(item));",
    '  return { mode: "implicit", required, optional };',
    "}",
    "",
    "function selectBackendBinding(capability: GeneratedCapabilityRuntimeMetadata): GeneratedBackendBinding | null {",
    "  if (capability.backend_bindings.length === 0) return null;",
    "  if (capability.backend_bindings.length === 1) return capability.backend_bindings[0];",
    "  const configured = activeSelections[capability.capability_id];",
    "  if (!configured) return capability.backend_bindings[0];",
    "  const selected = capability.backend_bindings.find(",
    "    (binding) =>",
    "      (!configured.backend_kind || configured.backend_kind === binding.backend_kind)",
    "      && (!configured.connection_ref || configured.connection_ref === binding.connection_ref),",
    "  );",
    '  if (!selected) throw new Error(`Configured backend selection does not match ${capability.capability_id}.`);',
    "  return selected;",
    "}",
    "",
    "function buildBackendInvocationPlan(capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>): BackendInvocationPlan {",
    "  const selectedBinding = selectBackendBinding(capability);",
    "  const backendInputContract = effectiveBackendInputContract(capability, selectedBinding);",
    "  const semanticKeys = new Set([",
    "    ...capability.required_inputs.map((input) => input.input_name),",
    "    ...capability.optional_inputs.map((input) => input.input_name),",
    "  ]);",
    "  const semanticInput = Object.fromEntries(Object.entries(params).filter(([key]) => semanticKeys.has(key)));",
    "  const unresolved = backendInputContract.required.filter((key) => !(key in params));",
    "  return {",
    "    selected_binding: selectedBinding,",
    "    semantic_input: semanticInput,",
    "    backend_input_contract: backendInputContract,",
    "    unresolved_required_backend_inputs: unresolved,",
    "  };",
    "}",
    "",
    "function assertRequiredSemanticInputs(capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>) {",
    "  const missing = capability.required_inputs.filter((input) => params[input.input_name] === undefined || params[input.input_name] === null || params[input.input_name] === \"\");",
    "  if (missing.length === 0) return;",
    "  throw new ANIPError(",
    '    "clarification_required",',
    '    `Required semantic inputs are missing for ${capability.capability_id}.`,',
    "    {",
    '      action: "clarify",',
    "      missing_inputs: missing.map((input) => input.input_name),",
    "      required_by: capability.capability_id,",
    "    },",
    "    false,",
    "  );",
    "}",
    "",
    'function sideEffectType(sideEffectLevel: string): "read" | "write" | "irreversible" | "transactional" {',
    '  if (sideEffectLevel.includes("irreversible")) return "irreversible";',
    '  if (sideEffectLevel.includes("transaction")) return "transactional";',
    '  if (sideEffectLevel.includes("write")) return "write";',
    '  return "read";',
    "}",
    "",
    "async function handleGeneratedCapability(capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>) {",
    "  assertRequiredSemanticInputs(capability, params);",
    "  const policy = await evaluatePolicy({ capability, params });",
    '  if (policy.decision === "deny") {',
    '    throw new ANIPError("access_denied", policy.detail || `Request denied for ${capability.capability_id}.`, policy.resolution, false);',
    "  }",
    '  if (policy.decision === "clarify") {',
    '    throw new ANIPError("clarification_required", policy.detail || `Clarification required for ${capability.capability_id}.`, policy.resolution, false);',
    "  }",
    "  const plan = buildBackendInvocationPlan(capability, params);",
    '  if (policy.decision === "approval_required" || capability.execution_posture === "approval_gated") {',
    "    return {",
    '      execution_status: "approval_required",',
    "      capability_id: capability.capability_id,",
    "      title: capability.title,",
    "      summary: capability.summary,",
    "      semantic_input: plan.semantic_input,",
    "      backend_input_contract: plan.backend_input_contract,",
    "      approval_rule_refs: capability.governance.approval_rule_refs,",
    '      note: "Generated host requires approval before backend execution.",',
    "    };",
    "  }",
    '  if (capability.execution_posture === "prepare_only") {',
    "    return {",
    '      execution_status: "prepared",',
    "      capability_id: capability.capability_id,",
    "      semantic_input: plan.semantic_input,",
    "      backend_input_contract: plan.backend_input_contract,",
    '      note: "Generated host prepared a governed preview and did not execute the backend.",',
    "    };",
    "  }",
    "  return backendAdapter.execute(capability, plan, params);",
    "}",
    "",
    "export const generatedCapabilities: CapabilityDef[] = generatedCapabilityMetadata.map((capability) => defineCapability({",
    "  declaration: {",
    "    name: capability.capability_id,",
    "    description: capability.summary,",
    '    contract_version: "1.0",',
    "    inputs: [",
    "      ...capability.required_inputs.map((input) => ({",
    "        name: input.input_name,",
    '        type: input.input_type || "string",',
    "        required: true,",
    "        default: null,",
    "        description: input.summary || input.input_name,",
    "      })),",
    "      ...capability.optional_inputs.map((input) => ({",
    "        name: input.input_name,",
    '        type: input.input_type || "string",',
    "        required: false,",
    "        default: null,",
    "        description: input.summary || input.input_name,",
    "      })),",
    "    ],",
    "    output: {",
    '      type: capability.output_shape || "governed_result",',
    '      fields: ["execution_status", "capability_id", "semantic_input"],',
    "    },",
    "    side_effect: { type: sideEffectType(capability.side_effect_level), rollback_window: null },",
    "    minimum_scope: capability.minimum_scope,",
    "    cost: null,",
    "    requires: [],",
    "    composes_with: [],",
    '    session: { type: "stateless" },',
    "    observability: null,",
    '    response_modes: ["unary"],',
    "    requires_binding: [],",
    "    control_requirements: [],",
    "    refresh_via: [],",
    "    verify_via: [],",
    "    cross_service: null,",
    "  },",
    "  handler: async (_ctx, params) => handleGeneratedCapability(capability, params),",
    "}));",
    "",
    "export { generatedCapabilityMetadata };",
    "",
  ].join("\n");
}

function buildGeneratedBackendAdapterModule(): string {
  return [
    'import type { BackendInvocationPlan, GeneratedCapabilityRuntimeMetadata } from "../generated/runtime-target.js";',
    "",
    "export interface GeneratedBackendAdapter {",
    "  execute(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, params: Record<string, unknown>): Promise<Record<string, unknown>>;",
    "}",
    "",
    "export function createDefaultBackendAdapter(): GeneratedBackendAdapter {",
    "  return {",
    "    async execute(capability, plan, _params) {",
    "      if (plan.unresolved_required_backend_inputs.length > 0) {",
    "        return {",
    '          execution_status: "backend_input_incomplete",',
    "          capability_id: capability.capability_id,",
    "          backend_input_contract: plan.backend_input_contract,",
    "          unresolved_required_backend_inputs: plan.unresolved_required_backend_inputs,",
    '          note: "Generated host is runnable, but backend-only inputs still require extension completion.",',
    "        };",
    "      }",
    "      return {",
    '        execution_status: "backend_execution_stub",',
    "        capability_id: capability.capability_id,",
    "        selected_backend: plan.selected_binding,",
    "        semantic_input: plan.semantic_input,",
    "        backend_input_contract: plan.backend_input_contract,",
    '        note: "Replace createDefaultBackendAdapter() with provider-specific backend execution.",',
    "      };",
    "    },",
    "  };",
    "}",
    "",
    "export const backendAdapter = createDefaultBackendAdapter();",
    "",
  ].join("\n");
}

function buildGeneratedPolicyModule(): string {
  return [
    'import type { GeneratedCapabilityRuntimeMetadata } from "../generated/runtime-target.js";',
    "",
    "export type PolicyDecision = {",
    '  decision: "allow" | "deny" | "clarify" | "approval_required";',
    "  detail?: string;",
    "  resolution?: Record<string, unknown>;",
    "};",
    "",
    "export async function evaluatePolicy(_context: {",
    "  capability: GeneratedCapabilityRuntimeMetadata;",
    "  params: Record<string, unknown>;",
    "}): Promise<PolicyDecision> {",
    '  return { decision: "allow" };',
    "}",
    "",
  ].join("\n");
}

function buildGeneratedAppModule(): string {
  return [
    'import { resolve, dirname } from "node:path";',
    'import { fileURLToPath } from "node:url";',
    'import { Hono } from "hono";',
    'import { createANIPService } from "@anip-dev/service";',
    'import { mountAnip } from "@anip-dev/hono";',
    'import { generatedCapabilities } from "./generated/capabilities.js";',
    'import { runtimeTarget } from "./generated/runtime-target.js";',
    "",
    "const __dirname = dirname(fileURLToPath(import.meta.url));",
    "",
    "function readApiKeys(): Record<string, string> {",
    '  const raw = process.env.ANIP_API_KEYS_JSON;',
    '  if (!raw) return { "dev-admin-key": "human:local-developer" };',
    "  try {",
    '    return JSON.parse(raw) as Record<string, string>;',
    "  } catch {",
    '    return { "dev-admin-key": "human:local-developer" };',
    "  }",
    "}",
    "",
    "const apiKeys = readApiKeys();",
    'const serviceId = process.env.ANIP_SERVICE_ID ?? runtimeTarget.system_name;',
    "",
    "export const service = createANIPService({",
    "  serviceId,",
    "  capabilities: generatedCapabilities,",
    '  trust: (process.env.ANIP_TRUST_LEVEL as "signed" | "anchored") ?? "signed",',
    '  keyPath: process.env.ANIP_KEY_PATH ?? resolve(__dirname, "../anip-keys"),',
    '  storage: { type: process.env.ANIP_STORAGE === "sqlite" ? "sqlite" : "memory" },',
    '  authenticate: async (bearer: string) => apiKeys[bearer] ?? null,',
    "});",
    "",
    "export const app = new Hono();",
    "const mounted = await mountAnip(app, service, { healthEndpoint: true });",
    "export const stop = mounted.stop;",
    "",
  ].join("\n");
}

function buildGeneratedMainModule(port: number, systemName: string): string {
  const displayName = titleCase(systemName.replace(/[-_]+/g, " "));
  return [
    'import { serve } from "@hono/node-server";',
    'import { app, stop } from "./app.js";',
    "",
    `const defaultPort = ${port};`,
    "const port = Number(process.env.PORT || defaultPort);",
    `const label = ${JSON.stringify(displayName)};`,
    "",
    "const server = serve({ fetch: app.fetch, port }, (info) => {",
    '  console.log(`${label} running on http://localhost:${info.port}`);',
    "});",
    "",
    'process.on("SIGINT", () => {',
    "  stop();",
    "  server.close();",
    "});",
    "",
  ].join("\n");
}

function buildGeneratedSmokeTestModule(): string {
  return [
    'import { describe, expect, it } from "vitest";',
    'import { app } from "../src/app.js";',
    'import { generatedCapabilityMetadata } from "../src/generated/runtime-target.js";',
    "",
    "async function issueToken(capabilityId: string, scope: string[]) {",
    '  const response = await app.request("/anip/tokens", {',
    '    method: "POST",',
    "    headers: {",
    '      authorization: "Bearer dev-admin-key",',
    '      "content-type": "application/json",',
    "    },",
    '    body: JSON.stringify({ capability: capabilityId, scope, subject: "test-agent" }),',
    "  });",
    "  expect(response.status).toBe(200);",
    "  const body = await response.json() as { token: string };",
    "  return body.token;",
    "}",
    "",
    'describe("generated ANIP service", () => {',
    '  it("serves discovery", async () => {',
    '    const response = await app.request("/.well-known/anip");',
    "    expect(response.status).toBe(200);",
    "    const body = await response.json() as { anip_discovery: { capabilities: Record<string, unknown> } };",
    "    expect(body.anip_discovery.capabilities[generatedCapabilityMetadata[0].capability_id]).toBeDefined();",
    "  });",
    "",
    '  it("invokes the first generated capability", async () => {',
    "    const capability = generatedCapabilityMetadata[0];",
    "    const token = await issueToken(capability.capability_id, capability.minimum_scope);",
    "    const response = await app.request(`/anip/invoke/${capability.capability_id}`, {",
    '      method: "POST",',
    "      headers: {",
    '        authorization: `Bearer ${token}`,',
    '        "content-type": "application/json",',
    "      },",
    "      body: JSON.stringify({ parameters: capability.sample_parameters }),",
    "    });",
    "    expect(response.status).toBe(200);",
    "    const body = await response.json() as { success: boolean; result: { execution_status?: string } };",
    "    expect(body.success).toBe(true);",
    "    expect(body.result.execution_status).toBeTruthy();",
    "  });",
    "});",
    "",
  ].join("\n");
}

function uniqueStrings(values: string[]): string[] {
  return Array.from(new Set(values.filter((value) => typeof value === "string" && value.trim())));
}

function titleCase(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function systemNameToPackageName(systemName: string): string {
  return systemName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "generated-anip-service";
}
