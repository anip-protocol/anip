package generator

import (
	"encoding/json"
	"fmt"
	"path/filepath"
	"runtime"
	"strings"
)

const (
	anipTypeScriptPackageVersion = "0.24.5"
	defaultGeneratorPort         = 4100
)

func BuildTypeScriptProject(definition *AnipServiceDefinition, options BuildTypeScriptProjectOptions) (*GeneratedProject, error) {
	model, err := BuildGenerationModel(definition)
	if err != nil {
		return nil, err
	}
	systemName := model.SystemName
	if systemName == "" {
		systemName = "generated-anip-service"
	}
	packageName := strings.TrimSpace(options.PackageName)
	if packageName == "" {
		packageName = systemNameToPackageName(systemName)
	}
	if options.DependencySource == "" {
		options.DependencySource = DependencySourceRegistry
	}
	if options.HttpRuntime == "" {
		options.HttpRuntime = HttpRuntimeHono
	}
	transports, err := normalizeTransports(options.Transports)
	if err != nil {
		return nil, err
	}
	if options.Port == 0 {
		options.Port = defaultGeneratorPort
	}
	if err := validateDependencySource(options.DependencySource); err != nil {
		return nil, err
	}
	if err := validateGeneratedPort(options.Port); err != nil {
		return nil, err
	}
	if err := validateNpmPackageName(packageName); err != nil {
		return nil, err
	}
	if err := validateTypeScriptRuntime(options.HttpRuntime); err != nil {
		return nil, err
	}

	project := &GeneratedProject{
		PackageName: packageName,
		SystemName:  systemName,
		Framework:   string(options.HttpRuntime),
		Transports:  TransportNames(transports),
		Files: []GeneratedFile{
			{Path: "package.json", Content: buildGeneratedPackageJSON(packageName, options.DependencySource, options.HttpRuntime, transports)},
			{Path: "tsconfig.json", Content: buildGeneratedTSConfig()},
			{Path: "vitest.config.ts", Content: buildGeneratedVitestConfig()},
			{Path: "README.md", Content: buildGeneratedReadme(systemName, options.HttpRuntime, transports)},
			{Path: "anip-service-definition.json", Content: string(model.DefinitionJSON)},
			{Path: "src/generated/service-definition.ts", Content: buildGeneratedServiceDefinitionModule(string(model.DefinitionJSON))},
			{Path: "src/generated/runtime-target.ts", Content: buildGeneratedRuntimeTargetModule(string(model.RuntimeTargetJSON), string(model.CapabilitiesJSON))},
			{Path: "src/generated/capabilities.ts", Content: buildGeneratedCapabilitiesModule()},
			{Path: "src/runtime/backend-adapter.ts", Content: buildGeneratedBackendAdapterModule()},
			{Path: "src/runtime/policy.ts", Content: buildGeneratedPolicyModule()},
			{Path: "src/app.ts", Content: buildGeneratedAppModule(options.HttpRuntime)},
			{Path: "src/main.ts", Content: buildGeneratedMainModule(options.Port, systemName, options.HttpRuntime)},
			{Path: "tests/service-smoke.test.ts", Content: buildGeneratedSmokeTestModule(options.HttpRuntime)},
		},
	}
	if hasTransport(transports, TransportStdio) {
		project.Files = append(project.Files, GeneratedFile{Path: "src/stdio.ts", Content: buildGeneratedTypeScriptStdioModule()})
	}
	project.Files = append(project.Files, buildIntegrationFrontingArtifacts(model)...)
	return project, nil
}

func buildGeneratedPackageJSON(packageName string, dependencySource DependencySource, runtime HttpRuntime, transports []Transport) string {
	var dependencies map[string]string
	if dependencySource == DependencySourceLocal {
		dependencies = map[string]string{
			"@anip-dev/core":    localTypeScriptDependencyPath("core"),
			"@anip-dev/crypto":  localTypeScriptDependencyPath("crypto"),
			"@anip-dev/server":  localTypeScriptDependencyPath("server"),
			"@anip-dev/service": localTypeScriptDependencyPath("service"),
		}
		addTypeScriptRuntimeDependencies(dependencies, runtime, true)
		if hasTransport(transports, TransportStdio) {
			dependencies["@anip-dev/stdio"] = localTypeScriptDependencyPath("stdio")
		}
	} else {
		dependencies = map[string]string{
			"@anip-dev/service": anipTypeScriptPackageVersion,
		}
		addTypeScriptRuntimeDependencies(dependencies, runtime, false)
		if hasTransport(transports, TransportStdio) {
			dependencies["@anip-dev/stdio"] = anipTypeScriptPackageVersion
		}
	}

	devDependencies := map[string]string{
		"@types/node": "^22.0.0",
		"tsx":         "^4.20.6",
		"typescript":  "^5.5.0",
		"vitest":      "^4.1.0",
	}
	if runtime == HttpRuntimeExpress {
		devDependencies["@types/supertest"] = "^6.0.3"
		devDependencies["supertest"] = "^7.0.0"
	}

	scripts := map[string]string{
		"dev":   "tsx src/main.ts",
		"build": "tsc -p tsconfig.json",
		"start": "node dist/main.js",
		"test":  "vitest run",
	}
	if hasTransport(transports, TransportStdio) {
		scripts["stdio"] = "tsx src/stdio.ts"
		scripts["start:stdio"] = "node dist/stdio.js"
	}

	payload := map[string]any{
		"name":            packageName,
		"private":         true,
		"version":         "0.1.0",
		"type":            "module",
		"scripts":         scripts,
		"dependencies":    dependencies,
		"devDependencies": devDependencies,
	}
	content, _ := marshalIndented(payload)
	return string(content)
}

func addTypeScriptRuntimeDependencies(dependencies map[string]string, runtime HttpRuntime, local bool) {
	switch runtime {
	case HttpRuntimeExpress:
		if local {
			dependencies["@anip-dev/express"] = localTypeScriptDependencyPath("express")
			dependencies["express"] = localTypeScriptDependencyPath("node_modules", "express")
		} else {
			dependencies["@anip-dev/express"] = anipTypeScriptPackageVersion
			dependencies["express"] = "^5.0.1"
		}
	case HttpRuntimeFastify:
		if local {
			dependencies["@anip-dev/fastify"] = localTypeScriptDependencyPath("fastify")
			dependencies["fastify"] = localTypeScriptDependencyPath("node_modules", "fastify")
		} else {
			dependencies["@anip-dev/fastify"] = anipTypeScriptPackageVersion
			dependencies["fastify"] = "^5.1.0"
		}
	default:
		if local {
			dependencies["@anip-dev/hono"] = localTypeScriptDependencyPath("hono")
			dependencies["hono"] = localTypeScriptDependencyPath("node_modules", "hono")
			dependencies["@hono/node-server"] = localTypeScriptDependencyPath("node_modules", "@hono", "node-server")
		} else {
			dependencies["@anip-dev/hono"] = anipTypeScriptPackageVersion
			dependencies["@hono/node-server"] = "^1.11.0"
			dependencies["hono"] = "^4.12.8"
		}
	}
}

func buildGeneratedTSConfig() string {
	payload := map[string]any{
		"compilerOptions": map[string]any{
			"target":           "ES2022",
			"module":           "Node16",
			"moduleResolution": "Node16",
			"declaration":      true,
			"sourceMap":        true,
			"strict":           true,
			"esModuleInterop":  true,
			"skipLibCheck":     true,
			"outDir":           "dist",
			"rootDir":          "src",
		},
		"include": []string{"src"},
	}
	content, _ := marshalIndented(payload)
	return string(content)
}

func buildGeneratedVitestConfig() string {
	return strings.Join([]string{
		`import { defineConfig } from "vitest/config";`,
		"",
		"export default defineConfig({",
		"  test: {",
		`    include: ["tests/**/*.test.ts"],`,
		"  },",
		"});",
		"",
	}, "\n")
}

func buildGeneratedReadme(systemName string, runtime HttpRuntime, transports []Transport) string {
	runtimePackage := "@anip-dev/hono"
	switch runtime {
	case HttpRuntimeExpress:
		runtimePackage = "@anip-dev/express"
	case HttpRuntimeFastify:
		runtimePackage = "@anip-dev/fastify"
	}
	lines := []string{
		"# " + titleCase(strings.NewReplacer("-", " ", "_", " ").Replace(systemName)),
		"",
		"Generated by `anip generate --target typescript --framework " + string(runtime) + "` from an exported `anip-service-definition.json`.",
		"",
		"## What is generated",
		"",
		"- " + titleCase(string(runtime)) + "-based ANIP HTTP host using `@anip-dev/service` and `" + runtimePackage + "`",
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
	}
	if hasTransport(transports, TransportStdio) {
		lines = append(lines, "- `npm run stdio`")
	}
	lines = append(lines, "")
	return strings.Join(lines, "\n")
}

func buildGeneratedServiceDefinitionModule(definitionJSON string) string {
	return strings.Join([]string{
		"// Generated from an exported ANIP Service Definition.",
		fmt.Sprintf("export const serviceDefinition = (%s) as const;", definitionJSON),
		"",
	}, "\n")
}

func buildGeneratedRuntimeTargetModule(runtimeTargetJSON, capabilityMetadataJSON string) string {
	return strings.Join([]string{
		"// Generated runtime target metadata.",
		"",
		"export type GeneratedBackendBinding = {",
		"  backend_kind: string;",
		"  connection_ref: string;",
		"  raw_operation_refs: string[];",
		`  backend_input_mode?: "implicit" | "hybrid" | "explicit";`,
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
		"  input_type?: string;",
		"  required?: boolean;",
		"  summary?: string;",
		"  default_value?: string;",
		"  allowed_values?: string[];",
		"  semantic_type?: string;",
		"  input_format?: string;",
		"  validation_pattern?: string;",
		"  clarification_hint?: string;",
		"  entity_reference?: boolean;",
		"  catalog_ref?: string;",
		"  input_meanings?: Array<{ value: string; label: string; description: string }>;",
		"  resolution?: Record<string, unknown>;",
		"  [key: string]: unknown;",
		"};",
		"",
		"export type GeneratedCapabilityRuntimeMetadata = {",
		"  service_id: string;",
		"  service_name: string;",
		"  capability_id: string;",
		"  title: string;",
		"  summary: string;",
		`  kind: "atomic" | "composed";`,
		"  composition?: Record<string, unknown> | null;",
		"  grant_policy?: Record<string, unknown> | null;",
		"  intent_type: string;",
		"  operation_type: string;",
		"  execution_posture: string;",
		"  side_effect_level: string;",
		"  implementation_fit?: { category?: string; rationale?: string };",
		"  business_effects?: { produces?: string[]; does_not_produce?: string[] };",
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
		`  backend_input_mode: "implicit" | "hybrid" | "explicit";`,
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
		"export type GeneratedPolicyBinding = {",
		"  id?: string;",
		"  actor_id?: string;",
		"  principal_selector?: { claim?: string; equals?: string };",
		"  capability_ids?: string[];",
		"  decision?: string;",
		"  business_rule?: string;",
		"  enforcement_notes?: string;",
		"};",
		"",
		"export type EffectiveBackendInputContract = {",
		`  mode: "implicit" | "hybrid" | "explicit";`,
		"  required: string[];",
		"  optional: string[];",
		"};",
		"",
		"export type BackendInvocationPlan = {",
		"  selected_binding: GeneratedBackendBinding | null;",
		"  semantic_input: Record<string, unknown>;",
		"  adapter_input: Record<string, unknown>;",
		"  backend_input_contract: EffectiveBackendInputContract;",
		"  unresolved_required_backend_inputs: string[];",
		"};",
		"",
		fmt.Sprintf("export const runtimeTarget = (%s) as const;", runtimeTargetJSON),
		"",
		fmt.Sprintf("export const generatedCapabilityMetadata: GeneratedCapabilityRuntimeMetadata[] = %s;", capabilityMetadataJSON),
		"",
	}, "\n")
}

func buildGeneratedCapabilitiesModule() string {
	return strings.Join([]string{
		`import { ANIPError, defineCapability, type CapabilityDef } from "@anip-dev/service";`,
		`import { backendAdapter } from "../runtime/backend-adapter.js";`,
		`import { evaluatePolicy } from "../runtime/policy.js";`,
		`import { generatedCapabilityMetadata, type BackendInvocationPlan, type EffectiveBackendInputContract, type GeneratedBackendBinding, type GeneratedCapabilityRuntimeMetadata } from "./runtime-target.js";`,
		"",
		"const activeSelections = readActiveSelections();",
		"",
		`function readActiveSelections(): Record<string, { backend_kind?: string; connection_ref?: string }> {`,
		`  const raw = process.env.ANIP_ACTIVE_BACKEND_SELECTIONS_JSON;`,
		"  if (!raw) return {};",
		"  try {",
		`    return JSON.parse(raw) as Record<string, { backend_kind?: string; connection_ref?: string }>;`,
		"  } catch {",
		"    return {};",
		"  }",
		"}",
		"",
		"function uniqueStrings(values: string[]) {",
		`  return Array.from(new Set(values.filter(Boolean)));`,
		"}",
		"",
		"function effectiveBackendInputContract(capability: GeneratedCapabilityRuntimeMetadata, selectedBinding: GeneratedBackendBinding | null): EffectiveBackendInputContract {",
		`  const mode = selectedBinding?.backend_input_mode || capability.backend_input_mode || "implicit";`,
		"  const derivedRequired = selectedBinding?.derived_required_backend_inputs?.length ? selectedBinding.derived_required_backend_inputs : capability.derived_required_backend_inputs;",
		"  const derivedOptional = selectedBinding?.derived_optional_backend_inputs?.length ? selectedBinding.derived_optional_backend_inputs : capability.derived_optional_backend_inputs;",
		"  const explicitRequired = selectedBinding?.explicit_required_backend_inputs?.length ? selectedBinding.explicit_required_backend_inputs : capability.explicit_required_backend_inputs;",
		"  const explicitOptional = selectedBinding?.explicit_optional_backend_inputs?.length ? selectedBinding.explicit_optional_backend_inputs : capability.explicit_optional_backend_inputs;",
		`  if (mode === "explicit") {`,
		"    const required = uniqueStrings(explicitRequired || []);",
		"    const optional = uniqueStrings((explicitOptional || []).filter((item) => !required.includes(item)));",
		`    return { mode: "explicit", required, optional };`,
		"  }",
		`  if (mode === "hybrid") {`,
		"    const required = uniqueStrings([...(derivedRequired || []), ...(explicitRequired || [])]);",
		"    const optional = uniqueStrings([...(derivedOptional || []), ...(explicitOptional || [])]).filter((item) => !required.includes(item));",
		`    return { mode: "hybrid", required, optional };`,
		"  }",
		"  const required = uniqueStrings(derivedRequired || []);",
		"  const optional = uniqueStrings(derivedOptional || []).filter((item) => !required.includes(item));",
		`  return { mode: "implicit", required, optional };`,
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
		"  if (!selected) throw new Error(`Configured backend selection does not match ${capability.capability_id}.`);",
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
		"  const adapterKeys = new Set([...semanticKeys, ...backendInputContract.required, ...backendInputContract.optional]);",
		"  const adapterInput = Object.fromEntries(Object.entries(params).filter(([key]) => adapterKeys.has(key)));",
		"  const unresolved = backendInputContract.required.filter((key) => !(key in params));",
		"  return {",
		"    selected_binding: selectedBinding,",
		"    semantic_input: semanticInput,",
		"    adapter_input: adapterInput,",
		"    backend_input_contract: backendInputContract,",
		"    unresolved_required_backend_inputs: unresolved,",
		"  };",
		"}",
		"",
		"function assertRequiredSemanticInputs(capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>) {",
		`  const missing = capability.required_inputs.filter((input) => !input.default_value && (params[input.input_name] === undefined || params[input.input_name] === null || params[input.input_name] === ""));`,
		"  if (missing.length === 0) return;",
		"  throw new ANIPError(",
		`    "clarification_required",`,
		"    `Required semantic inputs are missing for ${capability.capability_id}.`,",
		"    {",
		`      action: "obtain_binding",`,
		`      recovery_class: "refresh_then_retry",`,
		"      requires: missing.map((input) => input.input_name).join(\",\"),",
		"    },",
		"    false,",
		"  );",
		"}",
		"",
		"function applyInputDefaults(capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>) {",
		"  const normalized = { ...params };",
		"  for (const input of [...capability.required_inputs, ...capability.optional_inputs]) {",
		`    if (input.resolution?.on_missing === "omit") continue;`,
		`    if (input.default_value && (normalized[input.input_name] === undefined || normalized[input.input_name] === null || normalized[input.input_name] === "")) {`,
		"      normalized[input.input_name] = input.default_value;",
		"    }",
		"  }",
		"  return normalized;",
		"}",
		"",
		"function validateInputBehavior(capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>) {",
		"  for (const input of [...capability.required_inputs, ...capability.optional_inputs]) {",
		"    const value = params[input.input_name];",
		`    if (value === undefined || value === null || value === "") continue;`,
		"    const allowedValues = input.allowed_values || [];",
		"    if (allowedValues.length > 0 && !allowedValues.map(String).includes(String(value))) {",
		`      const shouldDeny = input.resolution?.mode === "closed_values" && input.resolution?.on_unresolved === "deny";`,
		"      throw new ANIPError(",
		`        shouldDeny ? "denied" : "clarification_required",`,
		"        input.summary || `Input ${input.input_name} must use one of the declared allowed values.`,",
		"        {",
		`          action: shouldDeny ? "contact_service_owner" : "obtain_binding",`,
		`          recovery_class: shouldDeny ? "terminal" : "refresh_then_retry",`,
		"          requires: input.input_name,",
		"        },",
		"        false,",
		"      );",
		"    }",
		"  }",
		"}",
		"",
		`function sideEffectType(sideEffectLevel: string): "read" | "write" | "irreversible" | "transactional" {`,
		`  if (sideEffectLevel.includes("irreversible")) return "irreversible";`,
		`  if (sideEffectLevel.includes("transaction")) return "transactional";`,
		`  if (sideEffectLevel.includes("write")) return "write";`,
		`  return "read";`,
		"}",
		"",
		"function inputResolution(value: Record<string, unknown> | undefined) {",
		"  if (!value) return null;",
		"  return {",
		"    mode: value.mode as any,",
		"    resolver_ref: typeof value.resolver_ref === \"string\" ? value.resolver_ref : null,",
		"    on_missing: (value.on_missing ?? null) as any,",
		"    on_ambiguous: (value.on_ambiguous ?? null) as any,",
		"    on_unresolved: (value.on_unresolved ?? null) as any,",
		"  };",
		"}",
		"",
		"async function handleGeneratedCapability(ctx: { rootPrincipal?: string; approvalGrant?: string | null }, capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>) {",
		"  params = applyInputDefaults(capability, params);",
		"  assertRequiredSemanticInputs(capability, params);",
		"  validateInputBehavior(capability, params);",
		"  const policy = await evaluatePolicy({ capability, params, rootPrincipal: ctx.rootPrincipal });",
		`  if (policy.decision === "deny") {`,
		"    throw new ANIPError(\"denied\", policy.detail || `Request denied for ${capability.capability_id}.`, policy.resolution || { action: \"contact_service_owner\", recovery_class: \"terminal\" }, false);",
		"  }",
		`  if (policy.decision === "clarify") {`,
		"    throw new ANIPError(\"clarification_required\", policy.detail || `Clarification required for ${capability.capability_id}.`, policy.resolution || { action: \"obtain_binding\", recovery_class: \"refresh_then_retry\" }, false);",
		"  }",
		"  const plan = buildBackendInvocationPlan(capability, params);",
		`  if (policy.decision === "approval_required" && !ctx.approvalGrant) {`,
		"    let preview: Record<string, unknown> = {};",
		"    try {",
		"      const candidatePreview = await backendAdapter.execute(capability, plan, plan.adapter_input, {",
		"        rootPrincipal: ctx.rootPrincipal,",
		"        approvalGrant: ctx.approvalGrant ?? null,",
		"      });",
		"      preview = candidatePreview && typeof candidatePreview === \"object\" && !Array.isArray(candidatePreview) ? candidatePreview : {};",
		"    } catch (err) {",
		"      if (!(err instanceof ANIPError) || err.errorType !== \"approval_required\") throw err;",
		"      const resolutionPreview = err.resolution?.preview;",
		"      const suppliedPreview = err.approvalRequired?.preview;",
		"      preview = suppliedPreview && typeof suppliedPreview === \"object\" && !Array.isArray(suppliedPreview)",
		"        ? suppliedPreview as Record<string, unknown>",
		"        : resolutionPreview && typeof resolutionPreview === \"object\" && !Array.isArray(resolutionPreview)",
		"          ? resolutionPreview as Record<string, unknown>",
		"          : {};",
		"    }",
		"    throw new ANIPError(\"approval_required\", policy.detail || `Approval required for ${capability.capability_id}.`, {",
		`      action: "request_approval",`,
		"      capability_id: capability.capability_id,",
		"      semantic_input: plan.semantic_input,",
		"      backend_input_contract: plan.backend_input_contract,",
		"      approval_rule_refs: capability.governance.approval_rule_refs,",
		"      preview,",
		"    }, false, { preview });",
		"  }",
		"  return backendAdapter.execute(capability, plan, plan.adapter_input, {",
		"    rootPrincipal: ctx.rootPrincipal,",
		"    approvalGrant: ctx.approvalGrant ?? null,",
		"  });",
		"}",
		"",
		"export const generatedCapabilities: CapabilityDef[] = generatedCapabilityMetadata.map((capability) => defineCapability({",
		"  declaration: {",
		"    name: capability.capability_id,",
		"    description: capability.summary,",
		`    contract_version: "1.0",`,
		"    inputs: [",
		"      ...capability.required_inputs.map((input) => ({",
		"        name: input.input_name,",
		`        type: input.input_type || "string",`,
		"        required: true,",
		"        default: input.default_value || null,",
		"        allowed_values: input.allowed_values || [],",
		"        semantic_type: input.semantic_type || null,",
		"        entity_reference: Boolean(input.entity_reference),",
		"        catalog_ref: input.catalog_ref || null,",
		"        input_meanings: input.input_meanings || null,",
		"        resolution: inputResolution(input.resolution),",
		"        description: input.summary || input.input_name,",
		"      })),",
		"      ...capability.optional_inputs.map((input) => ({",
		"        name: input.input_name,",
		`        type: input.input_type || "string",`,
		"        required: false,",
		"        default: input.default_value || null,",
		"        allowed_values: input.allowed_values || [],",
		"        semantic_type: input.semantic_type || null,",
		"        entity_reference: Boolean(input.entity_reference),",
		"        catalog_ref: input.catalog_ref || null,",
		"        input_meanings: input.input_meanings || null,",
		"        resolution: inputResolution(input.resolution),",
		"        description: input.summary || input.input_name,",
		"      })),",
		"    ],",
		"    output: {",
		`      type: capability.output_shape || "governed_result",`,
		`      fields: ["execution_status", "capability_id", "semantic_input"],`,
		"    },",
		"    side_effect: { type: sideEffectType(capability.side_effect_level), rollback_window: null },",
		"    minimum_scope: capability.minimum_scope,",
		"    cost: null,",
		"    requires: [],",
		"    composes_with: [],",
		`    session: { type: "stateless" },`,
		"    observability: null,",
		`    response_modes: ["unary"],`,
		"    requires_binding: [],",
		"    control_requirements: [],",
		"    refresh_via: [],",
		"    verify_via: [],",
		"    cross_service: null,",
		`    kind: capability.kind || "atomic",`,
		`    composition: (capability.composition ?? null) as CapabilityDef["declaration"]["composition"],`,
		`    grant_policy: (capability.grant_policy ?? null) as CapabilityDef["declaration"]["grant_policy"],`,
		"  },",
		"  handler: async (ctx, params) => handleGeneratedCapability(ctx, capability, params),",
		"}));",
		"",
		"export { generatedCapabilityMetadata };",
		"",
	}, "\n")
}

func buildGeneratedBackendAdapterModule() string {
	return strings.Join([]string{
		`import type { BackendInvocationPlan, GeneratedCapabilityRuntimeMetadata } from "../generated/runtime-target.js";`,
		"",
		"export type GeneratedBackendInvocationContext = {",
		"  rootPrincipal?: string;",
		"  approvalGrant?: string | null;",
		"};",
		"",
		"export interface GeneratedBackendAdapter {",
		"  execute(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, adapterInput: Record<string, unknown>, context: GeneratedBackendInvocationContext): Promise<Record<string, unknown>>;",
		"}",
		"",
		"export function createDefaultBackendAdapter(): GeneratedBackendAdapter {",
		"  return {",
		"    async execute(capability, plan, _adapterInput, _context) {",
		"      if (plan.unresolved_required_backend_inputs.length > 0) {",
		"        return {",
		`          execution_status: "backend_input_incomplete",`,
		"          capability_id: capability.capability_id,",
		"          backend_input_contract: plan.backend_input_contract,",
		"          unresolved_required_backend_inputs: plan.unresolved_required_backend_inputs,",
		`          note: "Generated host is runnable, but backend-only inputs still require extension completion.",`,
		"        };",
		"      }",
		`      if (capability.execution_posture === "approval_gated") {`,
		"        return {",
		`          execution_status: "approval_required",`,
		"          capability_id: capability.capability_id,",
		"          title: capability.title,",
		"          summary: capability.summary,",
		"          semantic_input: plan.semantic_input,",
		"          backend_input_contract: plan.backend_input_contract,",
		"          approval_rule_refs: capability.governance.approval_rule_refs,",
		`          note: "Generated host requires approval before backend execution.",`,
		"        };",
		"      }",
		`      if (capability.execution_posture === "prepare_only") {`,
		"        return {",
		`          execution_status: "prepared",`,
		"          capability_id: capability.capability_id,",
		"          semantic_input: plan.semantic_input,",
		"          backend_input_contract: plan.backend_input_contract,",
		`          note: "Generated host prepared a governed preview and did not execute the backend.",`,
		"        };",
		"      }",
		"      return {",
		`        execution_status: "backend_execution_stub",`,
		"        capability_id: capability.capability_id,",
		"        selected_backend: plan.selected_binding,",
		"        semantic_input: plan.semantic_input,",
		"        backend_input_contract: plan.backend_input_contract,",
		`        note: "Replace createDefaultBackendAdapter() with provider-specific backend execution.",`,
		"      };",
		"    },",
		"  };",
		"}",
		"",
		"export const backendAdapter = createDefaultBackendAdapter();",
		"",
	}, "\n")
}

func buildGeneratedPolicyModule() string {
	return strings.Join([]string{
		`import { runtimeTarget, type GeneratedCapabilityRuntimeMetadata, type GeneratedPolicyBinding } from "../generated/runtime-target.js";`,
		"",
		"export type PolicyDecision = {",
		`  decision: "allow" | "deny" | "clarify" | "approval_required";`,
		"  detail?: string;",
		"  resolution?: Record<string, unknown>;",
		"};",
		"",
		"const policyBindings = ((runtimeTarget as unknown as { policy_bindings?: GeneratedPolicyBinding[] }).policy_bindings ?? []);",
		"",
		"function principalClaims(rootPrincipal?: string): Record<string, string> {",
		"  const raw = (rootPrincipal ?? \"\").trim();",
		"  if (!raw) return {};",
		"  const pieces = raw.split(\"|\");",
		"  const claims: Record<string, string> = { principal: pieces[0] ?? \"\" };",
		"  for (const piece of pieces.slice(1)) {",
		"    const index = piece.indexOf(\"=\");",
		"    if (index < 0) continue;",
		"    claims[piece.slice(0, index).trim()] = piece.slice(index + 1).trim();",
		"  }",
		"  return claims;",
		"}",
		"",
		"function matchesPrincipal(binding: GeneratedPolicyBinding, claims: Record<string, string>): boolean {",
		"  const selector = binding.principal_selector ?? {};",
		"  const claim = selector.claim || \"actor_id\";",
		"  const expected = selector.equals || binding.actor_id || \"\";",
		"  if (!expected) return true;",
		"  if (!(claim in claims)) return false;",
		"  return claims[claim] === expected;",
		"}",
		"",
		"function requiresGovernedStop(capability: GeneratedCapabilityRuntimeMetadata): boolean {",
		"  return Boolean(capability.grant_policy)",
		"    || capability.side_effect_level === \"approval_required\"",
		"    || capability.execution_posture === \"approval_required\"",
		"    || capability.operation_type === \"approval_gated\";",
		"}",
		"",
		"function decisionFor(binding: GeneratedPolicyBinding): PolicyDecision {",
		"  const detail = binding.business_rule || binding.enforcement_notes;",
		"  if (binding.decision === \"deny\" || binding.decision === \"clarify\" || binding.decision === \"approval_required\") {",
		"    return { decision: binding.decision, detail };",
		"  }",
		"  return { decision: \"allow\", detail };",
		"}",
		"",
		"export async function evaluatePolicy(context: {",
		"  capability: GeneratedCapabilityRuntimeMetadata;",
		"  params: Record<string, unknown>;",
		"  rootPrincipal?: string;",
		"}): Promise<PolicyDecision> {",
		"  const bindings = policyBindings.filter((binding) => binding.capability_ids?.includes(context.capability.capability_id));",
		"  if (bindings.length === 0) return { decision: \"allow\" };",
		"  const claims = principalClaims(context.rootPrincipal);",
		"  if (Object.keys(claims).length === 0) return { decision: \"allow\" };",
		"  const matching = bindings.filter((binding) => matchesPrincipal(binding, claims));",
		"  if (requiresGovernedStop(context.capability)) {",
		"    const denied = matching.find((binding) => binding.decision === \"deny\");",
		"    if (denied) return decisionFor(denied);",
		"    const approval = matching.find((binding) => binding.decision === \"approval_required\");",
		"    if (approval) return decisionFor(approval);",
		"    const clarify = matching.find((binding) => binding.decision === \"clarify\");",
		"    if (clarify) return decisionFor(clarify);",
		"  }",
		"  const allowed = matching.find((binding) => binding.decision !== \"deny\" && binding.decision !== \"clarify\" && binding.decision !== \"approval_required\");",
		"  if (allowed) return decisionFor(allowed);",
		`  return { decision: "allow", detail: "No matching runtime policy binding; continuing." };`,
		"}",
		"",
	}, "\n")
}

func buildGeneratedAppModule(runtime HttpRuntime) string {
	switch runtime {
	case HttpRuntimeExpress:
		return buildGeneratedExpressAppModule()
	case HttpRuntimeFastify:
		return buildGeneratedFastifyAppModule()
	default:
		return buildGeneratedHonoAppModule()
	}
}

func buildGeneratedHonoAppModule() string {
	return strings.Join([]string{
		`import { resolve, dirname } from "node:path";`,
		`import { fileURLToPath } from "node:url";`,
		`import { Hono } from "hono";`,
		`import { createANIPService } from "@anip-dev/service";`,
		`import { mountAnip } from "@anip-dev/hono";`,
		`import { generatedCapabilities } from "./generated/capabilities.js";`,
		`import { runtimeTarget } from "./generated/runtime-target.js";`,
		"",
		"const __dirname = dirname(fileURLToPath(import.meta.url));",
		"",
		"function readApiKeys(): Record<string, string> {",
		`  const raw = process.env.ANIP_API_KEYS_JSON;`,
		`  if (!raw) return { "dev-admin-key": "human:local-developer" };`,
		"  try {",
		`    return JSON.parse(raw) as Record<string, string>;`,
		"  } catch {",
		`    return { "dev-admin-key": "human:local-developer" };`,
		"  }",
		"}",
		"",
		"const apiKeys = readApiKeys();",
		`const serviceId = process.env.ANIP_SERVICE_ID ?? runtimeTarget.system_name;`,
		"",
		"export const service = createANIPService({",
		"  serviceId,",
		"  capabilities: generatedCapabilities,",
		`  trust: (process.env.ANIP_TRUST_LEVEL as "signed" | "anchored") ?? "signed",`,
		`  keyPath: process.env.ANIP_KEY_PATH ?? resolve(__dirname, "../anip-keys"),`,
		`  storage: { type: process.env.ANIP_STORAGE === "sqlite" ? "sqlite" : "memory" },`,
		`  authenticate: async (bearer: string) => apiKeys[bearer] ?? null,`,
		"});",
		"",
		"export const app = new Hono();",
		"const mounted = await mountAnip(app, service, { healthEndpoint: true });",
		"export const stop = mounted.stop;",
		"",
	}, "\n")
}

func buildGeneratedExpressAppModule() string {
	return strings.Join([]string{
		`import { resolve, dirname } from "node:path";`,
		`import { fileURLToPath } from "node:url";`,
		`import express from "express";`,
		`import { createANIPService } from "@anip-dev/service";`,
		`import { mountAnip } from "@anip-dev/express";`,
		`import { generatedCapabilities } from "./generated/capabilities.js";`,
		`import { runtimeTarget } from "./generated/runtime-target.js";`,
		"",
		"const __dirname = dirname(fileURLToPath(import.meta.url));",
		"",
		"function readApiKeys(): Record<string, string> {",
		`  const raw = process.env.ANIP_API_KEYS_JSON;`,
		`  if (!raw) return { "dev-admin-key": "human:local-developer" };`,
		"  try {",
		`    return JSON.parse(raw) as Record<string, string>;`,
		"  } catch {",
		`    return { "dev-admin-key": "human:local-developer" };`,
		"  }",
		"}",
		"",
		"const apiKeys = readApiKeys();",
		`const serviceId = process.env.ANIP_SERVICE_ID ?? runtimeTarget.system_name;`,
		"",
		"export const service = createANIPService({",
		"  serviceId,",
		"  capabilities: generatedCapabilities,",
		`  trust: (process.env.ANIP_TRUST_LEVEL as "signed" | "anchored") ?? "signed",`,
		`  keyPath: process.env.ANIP_KEY_PATH ?? resolve(__dirname, "../anip-keys"),`,
		`  storage: { type: process.env.ANIP_STORAGE === "sqlite" ? "sqlite" : "memory" },`,
		`  authenticate: async (bearer: string) => apiKeys[bearer] ?? null,`,
		"});",
		"",
		"export const app = express();",
		"const mounted = await mountAnip(app, service, { healthEndpoint: true });",
		"export const stop = mounted.stop;",
		"",
	}, "\n")
}

func buildGeneratedFastifyAppModule() string {
	return strings.Join([]string{
		`import { resolve, dirname } from "node:path";`,
		`import { fileURLToPath } from "node:url";`,
		`import Fastify from "fastify";`,
		`import { createANIPService } from "@anip-dev/service";`,
		`import { mountAnip } from "@anip-dev/fastify";`,
		`import { generatedCapabilities } from "./generated/capabilities.js";`,
		`import { runtimeTarget } from "./generated/runtime-target.js";`,
		"",
		"const __dirname = dirname(fileURLToPath(import.meta.url));",
		"",
		"function readApiKeys(): Record<string, string> {",
		`  const raw = process.env.ANIP_API_KEYS_JSON;`,
		`  if (!raw) return { "dev-admin-key": "human:local-developer" };`,
		"  try {",
		`    return JSON.parse(raw) as Record<string, string>;`,
		"  } catch {",
		`    return { "dev-admin-key": "human:local-developer" };`,
		"  }",
		"}",
		"",
		"const apiKeys = readApiKeys();",
		`const serviceId = process.env.ANIP_SERVICE_ID ?? runtimeTarget.system_name;`,
		"",
		"export const service = createANIPService({",
		"  serviceId,",
		"  capabilities: generatedCapabilities,",
		`  trust: (process.env.ANIP_TRUST_LEVEL as "signed" | "anchored") ?? "signed",`,
		`  keyPath: process.env.ANIP_KEY_PATH ?? resolve(__dirname, "../anip-keys"),`,
		`  storage: { type: process.env.ANIP_STORAGE === "sqlite" ? "sqlite" : "memory" },`,
		`  authenticate: async (bearer: string) => apiKeys[bearer] ?? null,`,
		"});",
		"",
		"export const app = Fastify();",
		"const mounted = await mountAnip(app, service, { healthEndpoint: true });",
		"export const stop = mounted.stop;",
		"",
	}, "\n")
}

func buildGeneratedMainModule(port int, systemName string, runtime HttpRuntime) string {
	displayName := titleCase(strings.NewReplacer("-", " ", "_", " ").Replace(systemName))
	if runtime == HttpRuntimeExpress {
		return strings.Join([]string{
			`import { app, stop } from "./app.js";`,
			"",
			fmt.Sprintf("const defaultPort = %d;", port),
			"const port = Number(process.env.PORT || defaultPort);",
			fmt.Sprintf("const label = %q;", displayName),
			"",
			"const server = app.listen(port, () => {",
			"  console.log(`${label} running on http://localhost:${port}`);",
			"});",
			"",
			`process.on("SIGINT", () => {`,
			"  stop();",
			"  server.close();",
			"});",
			"",
		}, "\n")
	}
	if runtime == HttpRuntimeFastify {
		return strings.Join([]string{
			`import { app, stop } from "./app.js";`,
			"",
			fmt.Sprintf("const defaultPort = %d;", port),
			"const port = Number(process.env.PORT || defaultPort);",
			fmt.Sprintf("const label = %q;", displayName),
			"",
			"await app.listen({ host: \"0.0.0.0\", port });",
			"console.log(`${label} running on http://localhost:${port}`);",
			"",
			`process.on("SIGINT", async () => {`,
			"  stop();",
			"  await app.close();",
			"});",
			"",
		}, "\n")
	}
	return strings.Join([]string{
		`import { serve } from "@hono/node-server";`,
		`import { app, stop } from "./app.js";`,
		"",
		fmt.Sprintf("const defaultPort = %d;", port),
		"const port = Number(process.env.PORT || defaultPort);",
		fmt.Sprintf("const label = %q;", displayName),
		"",
		"const server = serve({ fetch: app.fetch, port }, (info) => {",
		"  console.log(`${label} running on http://localhost:${info.port}`);",
		"});",
		"",
		`process.on("SIGINT", () => {`,
		"  stop();",
		"  server.close();",
		"});",
		"",
	}, "\n")
}

func buildGeneratedTypeScriptStdioModule() string {
	return strings.Join([]string{
		`import { serveStdio } from "@anip-dev/stdio";`,
		`import { service, stop } from "./app.js";`,
		"",
		"try {",
		"  await serveStdio(service);",
		"} finally {",
		"  stop();",
		"}",
		"",
	}, "\n")
}

func buildGeneratedSmokeTestModule(runtime HttpRuntime) string {
	switch runtime {
	case HttpRuntimeExpress:
		return buildGeneratedExpressSmokeTestModule()
	case HttpRuntimeFastify:
		return buildGeneratedFastifySmokeTestModule()
	default:
		return buildGeneratedHonoSmokeTestModule()
	}
}

func buildGeneratedHonoSmokeTestModule() string {
	return strings.Join([]string{
		`import { describe, expect, it } from "vitest";`,
		`import { app } from "../src/app.js";`,
		`import { generatedCapabilityMetadata } from "../src/generated/runtime-target.js";`,
		"",
		"async function issueToken(capabilityId: string, scope: string[]) {",
		`  const response = await app.request("/anip/tokens", {`,
		`    method: "POST",`,
		"    headers: {",
		`      authorization: "Bearer dev-admin-key",`,
		`      "content-type": "application/json",`,
		"    },",
		`    body: JSON.stringify({ capability: capabilityId, scope, subject: "test-agent" }),`,
		"  });",
		"  expect(response.status).toBe(200);",
		"  const body = await response.json() as { token: string };",
		"  return body.token;",
		"}",
		"",
		`describe("generated ANIP service", () => {`,
		`  it("serves discovery", async () => {`,
		`    const response = await app.request("/.well-known/anip");`,
		"    expect(response.status).toBe(200);",
		"    const body = await response.json() as { anip_discovery: { capabilities: Record<string, unknown> } };",
		"    expect(body.anip_discovery.capabilities[generatedCapabilityMetadata[0].capability_id]).toBeDefined();",
		"  });",
		"",
		`  it("invokes the first generated capability", async () => {`,
		"    const capability = generatedCapabilityMetadata[0];",
		"    const token = await issueToken(capability.capability_id, capability.minimum_scope);",
		"    const response = await app.request(`/anip/invoke/${capability.capability_id}`, {",
		`      method: "POST",`,
		"      headers: {",
		"        authorization: `Bearer ${token}`,",
		`        "content-type": "application/json",`,
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
	}, "\n")
}

func buildGeneratedExpressSmokeTestModule() string {
	return strings.Join([]string{
		`import { describe, expect, it } from "vitest";`,
		`import request from "supertest";`,
		`import { app } from "../src/app.js";`,
		`import { generatedCapabilityMetadata } from "../src/generated/runtime-target.js";`,
		"",
		"async function issueToken(capabilityId: string, scope: string[]) {",
		`  const response = await request(app)`,
		`    .post("/anip/tokens")`,
		`    .set("Authorization", "Bearer dev-admin-key")`,
		`    .send({ capability: capabilityId, scope, subject: "test-agent" });`,
		"  expect(response.status).toBe(200);",
		"  return response.body.token as string;",
		"}",
		"",
		`describe("generated ANIP service", () => {`,
		`  it("serves discovery", async () => {`,
		`    const response = await request(app).get("/.well-known/anip");`,
		"    expect(response.status).toBe(200);",
		"    expect(response.body.anip_discovery.capabilities[generatedCapabilityMetadata[0].capability_id]).toBeDefined();",
		"  });",
		"",
		`  it("invokes the first generated capability", async () => {`,
		"    const capability = generatedCapabilityMetadata[0];",
		"    const token = await issueToken(capability.capability_id, capability.minimum_scope);",
		`    const response = await request(app)`,
		"      .post(`/anip/invoke/${capability.capability_id}`)",
		"      .set(\"Authorization\", `Bearer ${token}`)",
		"      .send({ parameters: capability.sample_parameters });",
		"    expect(response.status).toBe(200);",
		"    expect(response.body.success).toBe(true);",
		"    expect(response.body.result.execution_status).toBeTruthy();",
		"  });",
		"});",
		"",
	}, "\n")
}

func buildGeneratedFastifySmokeTestModule() string {
	return strings.Join([]string{
		`import { describe, expect, it } from "vitest";`,
		`import { app } from "../src/app.js";`,
		`import { generatedCapabilityMetadata } from "../src/generated/runtime-target.js";`,
		"",
		"async function issueToken(capabilityId: string, scope: string[]) {",
		`  const response = await app.inject({`,
		`    method: "POST",`,
		`    url: "/anip/tokens",`,
		`    headers: { authorization: "Bearer dev-admin-key" },`,
		`    payload: { capability: capabilityId, scope, subject: "test-agent" },`,
		"  });",
		"  expect(response.statusCode).toBe(200);",
		"  return response.json().token as string;",
		"}",
		"",
		`describe("generated ANIP service", () => {`,
		`  it("serves discovery", async () => {`,
		`    const response = await app.inject({ method: "GET", url: "/.well-known/anip" });`,
		"    expect(response.statusCode).toBe(200);",
		"    const body = response.json();",
		"    expect(body.anip_discovery.capabilities[generatedCapabilityMetadata[0].capability_id]).toBeDefined();",
		"  });",
		"",
		`  it("invokes the first generated capability", async () => {`,
		"    const capability = generatedCapabilityMetadata[0];",
		"    const token = await issueToken(capability.capability_id, capability.minimum_scope);",
		`    const response = await app.inject({`,
		`      method: "POST",`,
		"      url: `/anip/invoke/${capability.capability_id}`,",
		"      headers: { authorization: `Bearer ${token}` },",
		"      payload: { parameters: capability.sample_parameters },",
		"    });",
		"    expect(response.statusCode).toBe(200);",
		"    const body = response.json();",
		"    expect(body.success).toBe(true);",
		"    expect(body.result.execution_status).toBeTruthy();",
		"  });",
		"});",
		"",
	}, "\n")
}

func validateTypeScriptRuntime(runtime HttpRuntime) error {
	switch runtime {
	case HttpRuntimeHono, HttpRuntimeExpress, HttpRuntimeFastify:
		return nil
	default:
		return fmt.Errorf("unsupported TypeScript framework %q", runtime)
	}
}

func localTypeScriptDependencyPath(segments ...string) string {
	_, currentFile, _, _ := runtime.Caller(0)
	repoRoot := filepath.Clean(filepath.Join(filepath.Dir(currentFile), "..", "..", ".."))
	pathSegments := append([]string{repoRoot, "packages", "typescript"}, segments...)
	return "file:" + filepath.Join(pathSegments...)
}

func marshalIndented(value any) ([]byte, error) {
	content, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return nil, err
	}
	return append(content, '\n'), nil
}

func uniqueStrings(values []string) []string {
	if len(values) == 0 {
		return []string{}
	}
	seen := make(map[string]struct{}, len(values))
	result := make([]string, 0, len(values))
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value == "" {
			continue
		}
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		result = append(result, value)
	}
	return result
}

func fallbackString(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func fallbackStrings(values, fallback []string) []string {
	if len(values) == 0 {
		if fallback == nil {
			return nil
		}
		return append([]string{}, fallback...)
	}
	return append([]string{}, values...)
}

func titleCase(value string) string {
	parts := strings.Fields(value)
	for index, part := range parts {
		if part == "" {
			continue
		}
		parts[index] = strings.ToUpper(part[:1]) + part[1:]
	}
	return strings.Join(parts, " ")
}

func systemNameToPackageName(systemName string) string {
	lower := strings.ToLower(systemName)
	builder := strings.Builder{}
	lastDash := false
	for _, r := range lower {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			builder.WriteRune(r)
			lastDash = false
			continue
		}
		if !lastDash {
			builder.WriteRune('-')
			lastDash = true
		}
	}
	result := strings.Trim(builder.String(), "-")
	if result == "" {
		return "generated-anip-service"
	}
	return result
}

func parseNumber(text string) (any, bool) {
	if strings.Contains(text, ".") {
		var value float64
		if _, err := fmt.Sscanf(text, "%f", &value); err == nil {
			return value, true
		}
		return nil, false
	}
	var value int
	if _, err := fmt.Sscanf(text, "%d", &value); err == nil {
		return value, true
	}
	return nil, false
}
