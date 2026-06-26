package generator

import (
	"fmt"
	"path/filepath"
	"runtime"
	"strings"
)

const anipPythonPackageVersion = "0.24.6"

func BuildPythonProject(definition *AnipServiceDefinition, options BuildPythonProjectOptions) (*GeneratedProject, error) {
	model, err := BuildGenerationModel(definition)
	if err != nil {
		return nil, err
	}
	if options.DependencySource == "" {
		options.DependencySource = DependencySourceRegistry
	}
	transports, err := normalizeTransports(options.Transports)
	if err != nil {
		return nil, err
	}
	if options.Port == 0 {
		options.Port = defaultGeneratorPort
	}

	projectName := strings.TrimSpace(options.ProjectName)
	if projectName == "" {
		projectName = systemNameToPackageName(model.SystemName)
	}
	packageName := strings.TrimSpace(options.PackageName)
	if packageName == "" {
		packageName = pythonModuleName(model.SystemName)
	}
	if err := validateDependencySource(options.DependencySource); err != nil {
		return nil, err
	}
	if err := validateGeneratedPort(options.Port); err != nil {
		return nil, err
	}
	if err := validatePythonProjectName(projectName); err != nil {
		return nil, err
	}
	if err := validatePythonModuleName(packageName); err != nil {
		return nil, err
	}

	base := filepath.ToSlash(filepath.Join("src", packageName))
	services := model.RuntimeTarget.Services
	if len(services) == 0 {
		services = []GeneratedServiceMetadata{{
			ServiceID:   model.SystemName,
			ServiceName: titleCase(strings.NewReplacer("-", " ", "_", " ").Replace(model.SystemName)),
		}}
	}
	defaultServiceID := services[0].ServiceID

	project := &GeneratedProject{
		PackageName: projectName,
		SystemName:  model.SystemName,
		Transports:  TransportNames(transports),
		CustomBundleTemplateValues: map[string]string{
			"PYTHON_MODULE_NAME": packageName,
			"PACKAGE_NAME":       projectName,
		},
		Services: services,
		Files: []GeneratedFile{
			{Path: "pyproject.toml", Content: buildGeneratedPythonPyproject(projectName, packageName, options.DependencySource, transports)},
			{Path: "README.md", Content: buildGeneratedPythonReadme(model.SystemName, services, transports)},
			{Path: "anip-service-definition.json", Content: string(model.DefinitionJSON)},
			{Path: filepath.ToSlash(filepath.Join(base, "__init__.py")), Content: buildGeneratedPythonInit(packageName)},
			{Path: filepath.ToSlash(filepath.Join(base, "runtime_target.py")), Content: buildGeneratedPythonRuntimeTargetModule(string(model.RuntimeTargetJSON), string(model.CapabilitiesJSON))},
			{Path: filepath.ToSlash(filepath.Join(base, "backend_adapter.py")), Content: buildGeneratedPythonBackendAdapterModule()},
			{Path: filepath.ToSlash(filepath.Join(base, "policy.py")), Content: buildGeneratedPythonPolicyModule()},
			{Path: filepath.ToSlash(filepath.Join(base, "capabilities.py")), Content: buildGeneratedPythonCapabilitiesModule(defaultServiceID)},
			{Path: filepath.ToSlash(filepath.Join(base, "app.py")), Content: buildGeneratedPythonAppModule(defaultServiceID, options.Port)},
			{Path: filepath.ToSlash(filepath.Join(base, "services", "__init__.py")), Content: buildGeneratedPythonServicesInit()},
			{Path: "tests/test_service_smoke.py", Content: buildGeneratedPythonSmokeTestModule(packageName, model.Capabilities, services)},
		},
	}
	project.Files = append(project.Files, buildIntegrationFrontingArtifacts(model)...)
	for index, service := range services {
		if index == 0 {
			continue
		}
		serviceSlug := pythonModuleName(service.ServiceID)
		project.Files = append(project.Files,
			GeneratedFile{Path: filepath.ToSlash(filepath.Join(base, "services", serviceSlug, "__init__.py")), Content: ""},
			GeneratedFile{Path: filepath.ToSlash(filepath.Join(base, "services", serviceSlug, "app.py")), Content: buildGeneratedPythonServiceAppModule(service.ServiceID, options.Port)},
		)
	}
	if hasTransport(transports, TransportStdio) {
		project.Files = append(project.Files, GeneratedFile{Path: filepath.ToSlash(filepath.Join(base, "stdio_app.py")), Content: buildGeneratedPythonStdioAppModule()})
		upsertGeneratedFile(project, GeneratedFile{Path: "pyproject.toml", Content: buildGeneratedPythonPyproject(projectName, packageName, options.DependencySource, transports)})
		upsertGeneratedFile(project, GeneratedFile{Path: "README.md", Content: buildGeneratedPythonReadme(model.SystemName, services, transports)})
	}
	return project, nil
}

func buildGeneratedPythonPyproject(projectName, packageName string, dependencySource DependencySource, transports ...[]Transport) string {
	activeTransports := []Transport{TransportHTTP}
	if len(transports) > 0 {
		activeTransports = transports[0]
	}
	var dependencies []string
	if dependencySource == DependencySourceLocal {
		dependencies = []string{
			`"anip-core @ file://` + localPythonDependencyPath("anip-core") + `"`,
			`"anip-service @ file://` + localPythonDependencyPath("anip-service") + `"`,
			`"anip-fastapi @ file://` + localPythonDependencyPath("anip-fastapi") + `"`,
			`"fastapi>=0.115.0"`,
			`"uvicorn>=0.30.0"`,
		}
		if hasTransport(activeTransports, TransportStdio) {
			dependencies = append(dependencies, `"anip-stdio @ file://`+localPythonDependencyPath("anip-stdio")+`"`)
		}
	} else {
		dependencies = []string{
			fmt.Sprintf(`"anip-core==%s"`, anipPythonPackageVersion),
			fmt.Sprintf(`"anip-service==%s"`, anipPythonPackageVersion),
			fmt.Sprintf(`"anip-fastapi==%s"`, anipPythonPackageVersion),
			`"fastapi>=0.115.0"`,
			`"uvicorn>=0.30.0"`,
		}
		if hasTransport(activeTransports, TransportStdio) {
			dependencies = append(dependencies, fmt.Sprintf(`"anip-stdio==%s"`, anipPythonPackageVersion))
		}
	}

	lines := []string{
		"[project]",
		fmt.Sprintf("name = %q", projectName),
		`version = "0.1.0"`,
		`description = "Generated ANIP Python host"`,
		`requires-python = ">=3.11"`,
		"dependencies = [",
	}
	for _, dependency := range dependencies {
		lines = append(lines, "    "+dependency+",")
	}
	lines = append(lines,
		"]",
		"",
		"[project.optional-dependencies]",
		`dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "httpx>=0.27.0"]`,
		"",
		"[build-system]",
		`requires = ["setuptools>=68.0"]`,
		`build-backend = "setuptools.build_meta"`,
		"",
		"[tool.setuptools.packages.find]",
		`where = ["src"]`,
		`include = ["`+packageName+`*"]`,
		"",
		"[tool.pytest.ini_options]",
		`asyncio_mode = "auto"`,
		"",
	)
	return strings.Join(lines, "\n")
}

func buildGeneratedPythonReadme(systemName string, services []GeneratedServiceMetadata, transports ...[]Transport) string {
	activeTransports := []Transport{TransportHTTP}
	if len(transports) > 0 {
		activeTransports = transports[0]
	}
	serviceLines := []string{}
	for index, service := range services {
		module := pythonModuleName(systemName) + ".app"
		if index > 0 {
			module = pythonModuleName(systemName) + ".services." + pythonModuleName(service.ServiceID) + ".app"
		}
		serviceLines = append(serviceLines, "- `"+service.ServiceID+"`: `python -m "+module+"`")
	}
	if len(serviceLines) == 0 {
		serviceLines = append(serviceLines, "- `python -m "+pythonModuleName(systemName)+".app`")
	}
	lines := []string{
		"# " + titleCase(strings.NewReplacer("-", " ", "_", " ").Replace(systemName)),
		"",
		"Generated by `anip generate --target python` from an exported `anip-service-definition.json`.",
		"",
		"## What is generated",
		"",
		"- FastAPI-based ANIP host using `anip-service` and `anip-fastapi`",
		"- generated capability declarations and runtime routing",
		"- explicit backend adapter and policy seams for handwritten completion",
		"- smoke tests covering discovery and first-capability invocation for every contract service",
		"",
		"## Services",
		"",
		strings.Join(serviceLines, "\n"),
		"",
		"## Commands",
		"",
		"- `python -m " + pythonModuleName(systemName) + ".app`",
		"- `pytest`",
	}
	if hasTransport(activeTransports, TransportStdio) {
		lines = append(lines, "- `python -m "+pythonModuleName(systemName)+".stdio_app`")
	}
	lines = append(lines, "")
	return strings.Join(lines, "\n")
}

func buildGeneratedPythonInit(packageName string) string {
	return strings.Join([]string{
		`"""Generated ANIP Python host package."""`,
		`from .app import create_app, create_service`,
		"",
		`__all__ = ["create_app", "create_service"]`,
		"",
	}, "\n")
}

func buildGeneratedPythonRuntimeTargetModule(runtimeTargetJSON, capabilityMetadataJSON string) string {
	return strings.Join([]string{
		`"""Generated runtime target metadata."""`,
		"from __future__ import annotations",
		"",
		"import json",
		"",
		"RUNTIME_TARGET = json.loads(r'''" + runtimeTargetJSON + "''')",
		"GENERATED_RUNTIME_TARGET = RUNTIME_TARGET",
		"",
		"GENERATED_CAPABILITY_METADATA = json.loads(r'''" + capabilityMetadataJSON + "''')",
		"",
	}, "\n")
}

func buildGeneratedPythonBackendAdapterModule() string {
	return strings.Join([]string{
		`"""Backend execution seam for generated capabilities."""`,
		"from __future__ import annotations",
		"",
		"from typing import Any",
		"",
		"BackendInvocationPlan = dict[str, Any]",
		"GeneratedCapability = dict[str, Any]",
		"",
		"class DefaultBackendAdapter:",
		"    async def execute(self, capability: GeneratedCapability, plan: BackendInvocationPlan, _adapter_input: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:",
		`        if plan["unresolved_required_backend_inputs"]:`,
		"            return {",
		`                "execution_status": "backend_input_incomplete",`,
		`                "capability_id": capability["capability_id"],`,
		`                "backend_input_contract": plan["backend_input_contract"],`,
		`                "unresolved_required_backend_inputs": plan["unresolved_required_backend_inputs"],`,
		`                "note": "Generated host is runnable, but backend-only inputs still require extension completion.",`,
		"            }",
		`        if capability.get("execution_posture") == "approval_gated":`,
		"            return {",
		`                "execution_status": "approval_required",`,
		`                "capability_id": capability["capability_id"],`,
		`                "title": capability["title"],`,
		`                "summary": capability["summary"],`,
		`                "semantic_input": plan["semantic_input"],`,
		`                "backend_input_contract": plan["backend_input_contract"],`,
		`                "approval_rule_refs": capability.get("governance", {}).get("approval_rule_refs", []),`,
		`                "note": "Generated host requires approval before backend execution.",`,
		"            }",
		`        if capability.get("execution_posture") == "prepare_only":`,
		"            return {",
		`                "execution_status": "prepared",`,
		`                "capability_id": capability["capability_id"],`,
		`                "semantic_input": plan["semantic_input"],`,
		`                "backend_input_contract": plan["backend_input_contract"],`,
		`                "note": "Generated host prepared a governed preview and did not execute the backend.",`,
		"            }",
		"        return {",
		`            "execution_status": "backend_execution_stub",`,
		`            "capability_id": capability["capability_id"],`,
		`            "selected_backend": plan["selected_binding"],`,
		`            "semantic_input": plan["semantic_input"],`,
		`            "backend_input_contract": plan["backend_input_contract"],`,
		`            "note": "Replace DefaultBackendAdapter.execute() with provider-specific backend execution.",`,
		"        }",
		"",
		"backend_adapter = DefaultBackendAdapter()",
		"",
	}, "\n")
}

func buildGeneratedPythonPolicyModule() string {
	return strings.Join([]string{
		`"""Policy seam for generated capabilities."""`,
		"from __future__ import annotations",
		"",
		"from typing import Any",
		"",
		"from .runtime_target import GENERATED_RUNTIME_TARGET",
		"",
		"POLICY_BINDINGS = GENERATED_RUNTIME_TARGET.get('policy_bindings', [])",
		"",
		"def _principal_claims(root_principal: str | None) -> dict[str, str]:",
		"    raw = (root_principal or '').strip()",
		"    if not raw:",
		"        return {}",
		"    pieces = raw.split('|')",
		"    claims: dict[str, str] = {'principal': pieces[0]}",
		"    for piece in pieces[1:]:",
		"        if '=' not in piece:",
		"            continue",
		"        key, value = piece.split('=', 1)",
		"        claims[key.strip()] = value.strip()",
		"    return claims",
		"",
		"def _matches_principal(binding: dict[str, Any], claims: dict[str, str]) -> bool:",
		"    selector = binding.get('principal_selector') or {}",
		"    claim = str(selector.get('claim') or 'actor_id')",
		"    expected = str(selector.get('equals') or binding.get('actor_id') or '')",
		"    if not expected:",
		"        return True",
		"    if claim not in claims:",
		"        return False",
		"    return claims.get(claim) == expected",
		"",
		"def _requires_governed_stop(capability: dict[str, Any]) -> bool:",
		"    return bool(capability.get('grant_policy')) or capability.get('side_effect_level') == 'approval_required' or capability.get('execution_posture') == 'approval_required' or capability.get('operation_type') == 'approval_gated'",
		"",
		"def _decision_for(binding: dict[str, Any]) -> dict[str, Any]:",
		"    decision = str(binding.get('decision') or 'allow')",
		"    detail = binding.get('business_rule') or binding.get('enforcement_notes')",
		"    if decision == 'allow_with_limits':",
		"        return {'decision': 'allow', 'limits': binding, 'detail': detail}",
		"    if decision in {'deny', 'clarify', 'approval_required'}:",
		"        return {'decision': decision, 'detail': detail, 'policy_binding_id': binding.get('id')}",
		"    return {'decision': 'allow', 'policy_binding_id': binding.get('id'), 'detail': detail}",
		"",
		"async def evaluate_policy(context: dict[str, Any]) -> dict[str, Any]:",
		"    capability = context.get('capability') or {}",
		"    capability_id = capability.get('capability_id')",
		"    bindings = [binding for binding in POLICY_BINDINGS if capability_id in (binding.get('capability_ids') or [])]",
		"    if not bindings:",
		`        return {"decision": "allow"}`,
		"    claims = _principal_claims(context.get('root_principal'))",
		"    if not claims:",
		`        return {"decision": "allow", "note": "No actor claims were available for generated policy evaluation."}`,
		"    matching = [binding for binding in bindings if _matches_principal(binding, claims)]",
		"    if _requires_governed_stop(capability):",
		"        denied = next((binding for binding in matching if binding.get('decision') == 'deny'), None)",
		"        if denied:",
		"            return _decision_for(denied)",
		"        approval = next((binding for binding in matching if binding.get('decision') == 'approval_required'), None)",
		"        if approval:",
		"            return _decision_for(approval)",
		"        clarify = next((binding for binding in matching if binding.get('decision') == 'clarify'), None)",
		"        if clarify:",
		"            return _decision_for(clarify)",
		"    allowed = next((binding for binding in matching if binding.get('decision') not in {'deny', 'clarify', 'approval_required'}), None)",
		"    if allowed:",
		"        return _decision_for(allowed)",
		`    return {"decision": "allow", "detail": "No matching runtime policy binding; continuing."}`,
		"",
	}, "\n")
}

func buildGeneratedPythonServicesInit() string {
	return strings.Join([]string{
		`"""Generated per-service application modules."""`,
		"",
	}, "\n")
}

func buildGeneratedPythonCapabilitiesModule(defaultServiceID string) string {
	return strings.Join([]string{
		`"""Generated capability declarations and handlers."""`,
		"from __future__ import annotations",
		"",
		"import inspect",
		"import re",
		"from typing import Any",
		"",
		"from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SessionInfo, SideEffect",
		"from anip_service import ANIPError, Capability, InvocationContext",
		"",
		"from .backend_adapter import backend_adapter",
		"from .policy import evaluate_policy",
		"from .runtime_target import GENERATED_CAPABILITY_METADATA",
		"",
		fmt.Sprintf("DEFAULT_SERVICE_ID = %q", defaultServiceID),
		"",
		"def _first_non_empty(*values: str) -> str:",
		"    for value in values:",
		"        if isinstance(value, str) and value.strip():",
		"            return value",
		`    return ""`,
		"",
		"def _unique_strings(values: list[str]) -> list[str]:",
		"    result: list[str] = []",
		"    for value in values:",
		"        if not value or value in result:",
		"            continue",
		"        result.append(value)",
		"    return result",
		"",
		"def _effective_backend_input_contract(capability: dict[str, Any], selected_binding: dict[str, Any] | None) -> dict[str, Any]:",
		`    mode = (selected_binding or {}).get("backend_input_mode") or capability.get("backend_input_mode") or "implicit"`,
		`    derived_required = (selected_binding or {}).get("derived_required_backend_inputs") or capability.get("derived_required_backend_inputs", [])`,
		`    derived_optional = (selected_binding or {}).get("derived_optional_backend_inputs") or capability.get("derived_optional_backend_inputs", [])`,
		`    explicit_required = (selected_binding or {}).get("explicit_required_backend_inputs") or capability.get("explicit_required_backend_inputs", [])`,
		`    explicit_optional = (selected_binding or {}).get("explicit_optional_backend_inputs") or capability.get("explicit_optional_backend_inputs", [])`,
		`    if mode == "explicit":`,
		"        required = _unique_strings(explicit_required)",
		"        optional = [item for item in _unique_strings(explicit_optional) if item not in required]",
		`        return {"mode": "explicit", "required": required, "optional": optional}`,
		`    if mode == "hybrid":`,
		"        required = _unique_strings([*derived_required, *explicit_required])",
		"        optional = [item for item in _unique_strings([*derived_optional, *explicit_optional]) if item not in required]",
		`        return {"mode": "hybrid", "required": required, "optional": optional}`,
		"    required = _unique_strings(derived_required)",
		"    optional = [item for item in _unique_strings(derived_optional) if item not in required]",
		`    return {"mode": "implicit", "required": required, "optional": optional}`,
		"",
		"def generated_metadata_for_capability(capability_id: str) -> dict[str, Any]:",
		"    for metadata in GENERATED_CAPABILITY_METADATA:",
		"        if metadata.get('capability_id') == capability_id:",
		"            return metadata",
		"    raise KeyError(f'Unknown generated capability: {capability_id}')",
		"",
		"def generated_declaration_for_capability(capability_id: str) -> CapabilityDeclaration:",
		"    return _build_declaration(generated_metadata_for_capability(capability_id))",
		"",
		"def _select_backend_binding(capability: dict[str, Any]) -> dict[str, Any] | None:",
		`    bindings = capability.get("backend_bindings", [])`,
		"    if not bindings:",
		"        return None",
		"    return bindings[0]",
		"",
		"def _build_backend_invocation_plan(capability: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:",
		"    selected_binding = _select_backend_binding(capability)",
		"    contract = _effective_backend_input_contract(capability, selected_binding)",
		"    semantic_keys = {item['input_name'] for item in capability.get('required_inputs', [])} | {item['input_name'] for item in capability.get('optional_inputs', [])}",
		"    semantic_input = {key: value for key, value in params.items() if key in semantic_keys}",
		`    adapter_keys = semantic_keys | set(contract["required"]) | set(contract["optional"])`,
		"    adapter_input = {key: value for key, value in params.items() if key in adapter_keys}",
		"    unresolved = [key for key in contract['required'] if key not in params]",
		"    return {",
		`        "selected_binding": selected_binding,`,
		`        "semantic_input": semantic_input,`,
		`        "adapter_input": adapter_input,`,
		`        "backend_input_contract": contract,`,
		`        "unresolved_required_backend_inputs": unresolved,`,
		"    }",
		"",
		"def _capability_forbidden_effects(capability: dict[str, Any]) -> set[str]:",
		`    effects = capability.get("business_effects") or {}`,
		`    values = effects.get("does_not_produce") if isinstance(effects, dict) else []`,
		"    return {str(item) for item in values or [] if str(item or '').strip()}",
		"",
		"def _requested_effects(ctx: InvocationContext) -> set[str]:",
		`    values = getattr(ctx, "requested_effects", []) or []`,
		"    return {str(item) for item in values if str(item or '').strip()}",
		"",
		"def _assert_requested_effects_allowed(capability: dict[str, Any], ctx: InvocationContext) -> None:",
		"    requested = _requested_effects(ctx)",
		"    forbidden = _capability_forbidden_effects(capability)",
		"    blocked = sorted(requested & forbidden)",
		"    if blocked:",
		"        raise ANIPError(",
		`            "denied",`,
		`            f"Capability {capability['capability_id']} does not produce requested effect(s): {', '.join(blocked)}.",`,
		`            {"action": "request_declared_capability", "recovery_class": "terminal", "unsupported_effects": blocked},`,
		"            retry=False,",
		"        )",
		"",
		"def _assert_required_semantic_inputs(capability: dict[str, Any], params: dict[str, Any]) -> None:",
		"    missing = []",
		"    for item in capability.get('required_inputs', []):",
		"        resolution = item.get('resolution') or {}",
		`        if resolution.get("on_missing") in {"app_select_or_clarify"}:`,
		"            continue",
		"        if not item.get('default_value') and params.get(item['input_name']) in (None, ''):",
		"            missing.append(item['input_name'])",
		"    if missing:",
		"        raise ANIPError(",
		`            "clarification_required",`,
		`            f"Required semantic inputs are missing for {capability['capability_id']}.",`,
		`            {"action": "obtain_binding", "recovery_class": "refresh_then_retry", "requires": ",".join(missing)},`,
		"            retry=False,",
		"        )",
		"",
		"def _apply_input_defaults(capability: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:",
		"    normalized = dict(params)",
		"    for item in [*capability.get('required_inputs', []), *capability.get('optional_inputs', [])]:",
		"        name = item.get('input_name')",
		"        default_value = item.get('default_value')",
		`        resolution = item.get("resolution") or {}`,
		`        if resolution.get("on_missing") == "omit":`,
		"            continue",
		"        if name and default_value not in (None, '') and normalized.get(name) in (None, ''):",
		"            normalized[name] = default_value",
		"    return normalized",
		"",
		"def _validate_input_behavior(capability: dict[str, Any], params: dict[str, Any]) -> None:",
		"    for item in [*capability.get('required_inputs', []), *capability.get('optional_inputs', [])]:",
		"        name = item.get('input_name')",
		"        if not name or params.get(name) in (None, ''):",
		"            continue",
		"        value = params.get(name)",
		"        allowed_values = item.get('allowed_values') or []",
		"        if allowed_values and str(value) not in {str(allowed) for allowed in allowed_values}:",
		"            resolution = item.get('resolution') or {}",
		`            failure_type = "denied" if resolution.get("mode") == "closed_values" and resolution.get("on_unresolved") == "deny" else "clarification_required"`,
		`            action = "contact_service_owner" if failure_type == "denied" else "obtain_binding"`,
		`            recovery_class = "terminal" if failure_type == "denied" else "refresh_then_retry"`,
		"            raise ANIPError(",
		"                failure_type,",
		`                item.get("clarification_hint") or f"Input {name} must use one of the declared allowed values.",`,
		`                {"action": action, "recovery_class": recovery_class, "requires": name},`,
		"                retry=False,",
		"            )",
		"        pattern = item.get('validation_pattern')",
		`        if not pattern and item.get("input_format") == "business_quarter":`,
		`            pattern = r"^\d{4}-Q[1-4]$"`,
		"        if pattern and not re.match(str(pattern), str(value)):",
		"            raise ANIPError(",
		`                "clarification_required",`,
		`                item.get("clarification_hint") or f"Input {name} does not match the declared format.",`,
		`                {"action": "provide_valid_input", "requires": name, "format": item.get("input_format") or pattern},`,
		"                retry=False,",
		"            )",
		"",
		"def _side_effect_type(side_effect_level: str) -> str:",
		"    value = side_effect_level.lower()",
		`    if "irreversible" in value:`,
		`        return "irreversible"`,
		`    if "transaction" in value:`,
		`        return "transactional"`,
		`    if "write" in value:`,
		`        return "write"`,
		`    return "read"`,
		"",
		"def _resolve_json_path(payload: dict[str, Any], path: str | None) -> Any:",
		"    if not path or not path.startswith('$.'):",
		"        return None",
		"    current: Any = payload",
		"    for part in path[2:].split('.'):",
		"        if isinstance(current, dict) and part in current:",
		"            current = current[part]",
		"        else:",
		"            return None",
		"    return current",
		"",
		"def _is_empty_result(payload: Any) -> bool:",
		"    target = payload.get('result') if isinstance(payload, dict) else payload",
		"    if isinstance(target, dict):",
		"        if target.get('empty') is True:",
		"            return True",
		"        for key in ('accounts', 'items', 'rows', 'results', 'tasks'):",
		"            if key in target and target.get(key) == []:",
		"                return True",
		"    return target == []",
		"",
		"async def _invoke_composition_child(capability_registry: dict[str, Capability], capability_id: str, ctx: InvocationContext, params: dict[str, Any]) -> Any:",
		"    child = capability_registry.get(capability_id)",
		"    if child is None:",
		"        raise ANIPError('temporarily_unavailable', f'Generated composition child {capability_id} is not registered.')",
		"    result = child.handler(ctx, params)",
		"    if inspect.isawaitable(result):",
		"        result = await result",
		"    return result",
		"",
		"async def _execute_generated_composition(capability: dict[str, Any], ctx: InvocationContext, params: dict[str, Any], capability_registry: dict[str, Capability] | None) -> dict[str, Any]:",
		"    if capability_registry is None:",
		"        raise ANIPError('temporarily_unavailable', f'Generated composition {capability[\"capability_id\"]} requires a capability registry.')",
		"    composition = capability.get('composition') or {}",
		"    if composition.get('authority_boundary') != 'same_service':",
		"        raise ANIPError('temporarily_unavailable', 'Generated Python host only executes same-service composition locally.')",
		"    state: dict[str, Any] = {'steps': {}}",
		"    input_mapping = composition.get('input_mapping') or {}",
		"    for step in composition.get('steps') or []:",
		"        step_id = step.get('id')",
		"        child_capability = step.get('capability')",
		"        if not step_id or not child_capability:",
		"            raise ANIPError('temporarily_unavailable', 'Generated composition step is missing id or capability.')",
		"        child_params = dict(params)",
		"        mapping = input_mapping.get(step_id) or {}",
		"        mapping_root = {'input': params, 'steps': state['steps']}",
		"        if isinstance(mapping, dict):",
		"            for target_key, source_path in mapping.items():",
		"                if not isinstance(target_key, str) or not isinstance(source_path, str):",
		"                    continue",
		"                mapped_value = _resolve_json_path(mapping_root, source_path)",
		"                if mapped_value is not None:",
		"                    child_params[target_key] = mapped_value",
		"        child_output = await _invoke_composition_child(capability_registry, child_capability, ctx, child_params)",
		"        state['steps'][step_id] = {'output': child_output}",
		"        if step.get('empty_result_source') is True and _is_empty_result(child_output):",
		"            if composition.get('empty_result_policy') == 'return_success_no_results':",
		"                return composition.get('empty_result_output') or {'result': None, 'empty': True}",
		"    output_mapping = composition.get('output_mapping') or {}",
		"    resolved_output: dict[str, Any] = {}",
		"    if isinstance(output_mapping, dict):",
		"        for target_key, source_path in output_mapping.items():",
		"            if not isinstance(target_key, str) or not isinstance(source_path, str):",
		"                continue",
		"            mapped_value = _resolve_json_path(state, source_path)",
		"            if mapped_value is not None:",
		"                resolved_output[target_key] = mapped_value",
		"    if not resolved_output:",
		"        return {'result': state}",
		"    return resolved_output",
		"",
		"async def _handle_generated_capability(capability: dict[str, Any], ctx: InvocationContext, params: dict[str, Any], capability_registry: dict[str, Capability] | None = None) -> dict[str, Any]:",
		"    _assert_requested_effects_allowed(capability, ctx)",
		"    params = _apply_input_defaults(capability, params)",
		"    _assert_required_semantic_inputs(capability, params)",
		"    _validate_input_behavior(capability, params)",
		`    policy = await evaluate_policy({"capability": capability, "params": params, "root_principal": ctx.root_principal, "token": ctx.token})`,
		`    if policy.get("decision") == "deny":`,
		`        raise ANIPError("denied", policy.get("detail") or f"Request denied for {capability['capability_id']}.", {"action": "contact_service_owner", "recovery_class": "terminal"})`,
		`    if policy.get("decision") == "clarify":`,
		`        raise ANIPError("clarification_required", policy.get("detail") or f"Clarification required for {capability['capability_id']}.", {"action": "obtain_binding", "recovery_class": "refresh_then_retry"})`,
		`    if (capability.get("kind") or "atomic") == "composed":`,
		"        return await _execute_generated_composition(capability, ctx, params, capability_registry)",
		"    plan = _build_backend_invocation_plan(capability, params)",
		`    if policy.get("decision") == "approval_required":`,
		`        raise ANIPError("approval_required", policy.get("detail") or f"Approval required for {capability['capability_id']}.", {"action": "request_approval", "capability_id": capability["capability_id"], "semantic_input": plan["semantic_input"], "backend_input_contract": plan["backend_input_contract"], "approval_rule_refs": capability.get("governance", {}).get("approval_rule_refs", [])})`,
		`    return await backend_adapter.execute(capability, plan, plan["adapter_input"], ctx)`,
		"",
		"def _build_declaration(capability: dict[str, Any]) -> CapabilityDeclaration:",
		"    inputs = [",
		"        CapabilityInput(name=item['input_name'], type=item.get('input_type') or 'string', required=True, default=item.get('default_value') or None, allowed_values=item.get('allowed_values') or [], description=item.get('summary') or item['input_name'], semantic_type=item.get('semantic_type') or None, entity_reference=bool(item.get('entity_reference')), catalog_ref=item.get('catalog_ref') or None, resolution=item.get('resolution') or None)",
		"        for item in capability.get('required_inputs', [])",
		"    ] + [",
		"        CapabilityInput(name=item['input_name'], type=item.get('input_type') or 'string', required=False, default=item.get('default_value') or None, allowed_values=item.get('allowed_values') or [], description=item.get('summary') or item['input_name'], semantic_type=item.get('semantic_type') or None, entity_reference=bool(item.get('entity_reference')), catalog_ref=item.get('catalog_ref') or None, resolution=item.get('resolution') or None)",
		"        for item in capability.get('optional_inputs', [])",
		"    ]",
		"    rollback_window = 'not_applicable' if _side_effect_type(capability.get('side_effect_level', 'read')) == 'read' else 'none' if _side_effect_type(capability.get('side_effect_level', 'read')) == 'irreversible' else 'PT15M'",
		"    return CapabilityDeclaration(",
		`        name=capability["capability_id"],`,
		`        description=capability["summary"],`,
		`        contract_version="1.0",`,
		"        inputs=inputs,",
		"        output=CapabilityOutput(type=capability.get('output_shape') or 'governed_result', fields=['execution_status', 'capability_id', 'semantic_input']),",
		"        side_effect=SideEffect(type=_side_effect_type(capability.get('side_effect_level', 'read')), rollback_window=rollback_window),",
		`        minimum_scope=capability.get("minimum_scope", []),`,
		"        requires=[],",
		"        composes_with=[],",
		"        session=SessionInfo(type='stateless'),",
		"        response_modes=['unary'],",
		"        requires_binding=[],",
		"        control_requirements=[],",
		"        refresh_via=[],",
		"        verify_via=[],",
		`        kind=capability.get("kind") or "atomic",`,
		`        composition=capability.get("composition"),`,
		`        grant_policy=capability.get("grant_policy"),`,
		"    )",
		"",
		"def build_capabilities(service_id: str | None = None, capability_registry: dict[str, Capability] | None = None) -> list[Capability]:",
		"    capabilities: list[Capability] = []",
		"    registry: dict[str, Capability] = dict(capability_registry or {})",
		"    for metadata in GENERATED_CAPABILITY_METADATA:",
		"        if service_id is not None and metadata.get('service_id') != service_id:",
		"            continue",
		"        if metadata['capability_id'] in registry:",
		"            continue",
		"        async def handler(ctx: InvocationContext, params: dict[str, Any], capability: dict[str, Any] = metadata, registry: dict[str, Capability] = registry) -> dict[str, Any]:",
		"            return await _handle_generated_capability(capability, ctx, params, registry)",
		"        capability = Capability(declaration=_build_declaration(metadata), handler=handler)",
		"        capabilities.append(capability)",
		"        registry[metadata['capability_id']] = capability",
		"    return capabilities",
		"",
		"def generated_capabilities_for_service(service_id: str, capability_registry: dict[str, Capability] | None = None) -> list[Capability]:",
		"    return build_capabilities(service_id, capability_registry)",
		"",
		"generated_capabilities = generated_capabilities_for_service(DEFAULT_SERVICE_ID)",
		"",
	}, "\n")
}

func buildGeneratedPythonAppModule(defaultServiceID string, port int) string {
	if port == 0 {
		port = defaultGeneratorPort
	}
	return strings.Join([]string{
		`"""Generated FastAPI application entrypoint."""`,
		"from __future__ import annotations",
		"",
		"import os",
		"import uvicorn",
		"from fastapi import FastAPI",
		"from anip_fastapi import mount_anip",
		"from anip_service import ANIPService",
		"",
		"from .capabilities import generated_capabilities_for_service",
		"from .runtime_target import RUNTIME_TARGET",
		"",
		fmt.Sprintf("SERVICE_ID = %q", defaultServiceID),
		"",
		"def _api_keys() -> dict[str, str]:",
		`    raw = os.getenv("ANIP_API_KEYS_JSON")`,
		"    if not raw:",
		`        return {"dev-admin-key": "human:local-developer"}`,
		"    try:",
		"        import json",
		"        parsed = json.loads(raw)",
		"        if isinstance(parsed, dict):",
		"            return {str(key): str(value) for key, value in parsed.items()}",
		"    except Exception:",
		"        pass",
		`    return {"dev-admin-key": "human:local-developer"}`,
		"",
		"def _authenticate(bearer: str) -> str | None:",
		"    return _api_keys().get(bearer)",
		"",
		"def create_service() -> ANIPService:",
		"    return ANIPService(",
		"        service_id=SERVICE_ID,",
		"        capabilities=generated_capabilities_for_service(SERVICE_ID),",
		`        storage=":memory:",`,
		`        trust="signed",`,
		"        authenticate=_authenticate,",
		"    )",
		"",
		"def create_app() -> FastAPI:",
		"    app = FastAPI()",
		"    mount_anip(app, create_service(), health_endpoint=True)",
		"    return app",
		"",
		"app = create_app()",
		"",
		"if __name__ == '__main__':",
		fmt.Sprintf("    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '%d')))", port),
		"",
	}, "\n")
}

func buildGeneratedPythonServiceAppModule(serviceID string, port int) string {
	if port == 0 {
		port = defaultGeneratorPort
	}
	return strings.Join([]string{
		`"""Generated FastAPI application entrypoint for one contract service."""`,
		"from __future__ import annotations",
		"",
		"import os",
		"import uvicorn",
		"from fastapi import FastAPI",
		"from anip_fastapi import mount_anip",
		"from anip_service import ANIPService",
		"",
		"from ...capabilities import generated_capabilities_for_service",
		"",
		fmt.Sprintf("SERVICE_ID = %q", serviceID),
		"",
		"def _api_keys() -> dict[str, str]:",
		`    raw = os.getenv("ANIP_API_KEYS_JSON")`,
		"    if not raw:",
		`        return {"dev-admin-key": "human:local-developer"}`,
		"    try:",
		"        import json",
		"        parsed = json.loads(raw)",
		"        if isinstance(parsed, dict):",
		"            return {str(key): str(value) for key, value in parsed.items()}",
		"    except Exception:",
		"        pass",
		`    return {"dev-admin-key": "human:local-developer"}`,
		"",
		"def _authenticate(bearer: str) -> str | None:",
		"    return _api_keys().get(bearer)",
		"",
		"def create_service() -> ANIPService:",
		"    return ANIPService(",
		"        service_id=SERVICE_ID,",
		"        capabilities=generated_capabilities_for_service(SERVICE_ID),",
		`        storage=":memory:",`,
		`        trust="signed",`,
		"        authenticate=_authenticate,",
		"    )",
		"",
		"def create_app() -> FastAPI:",
		"    app = FastAPI()",
		"    mount_anip(app, create_service(), health_endpoint=True)",
		"    return app",
		"",
		"app = create_app()",
		"",
		"if __name__ == '__main__':",
		fmt.Sprintf("    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '%d')))", port),
		"",
	}, "\n")
}

func buildGeneratedPythonStdioAppModule() string {
	return strings.Join([]string{
		`"""Generated ANIP stdio entrypoint."""`,
		"from __future__ import annotations",
		"",
		"import asyncio",
		"",
		"from anip_stdio import serve_stdio",
		"",
		"from .app import create_service",
		"",
		"",
		"async def main() -> None:",
		"    await serve_stdio(create_service())",
		"",
		"",
		"if __name__ == '__main__':",
		"    asyncio.run(main())",
		"",
	}, "\n")
}

func buildGeneratedPythonSmokeTestModule(packageName string, capabilities []GeneratedCapabilityRuntimeMetadata, services []GeneratedServiceMetadata) string {
	serviceModules := make([]string, 0, len(services))
	for index, service := range services {
		module := packageName + ".app"
		if index > 0 {
			module = packageName + ".services." + pythonModuleName(service.ServiceID) + ".app"
		}
		serviceCapabilities := make([]string, 0)
		for _, capability := range capabilities {
			if capability.ServiceID == service.ServiceID {
				serviceCapabilities = append(serviceCapabilities, capability.CapabilityID)
			}
		}
		if len(serviceCapabilities) == 0 {
			continue
		}
		serviceModules = append(serviceModules, fmt.Sprintf(
			`    {"service_id": %q, "module": %q, "capabilities": %s},`,
			service.ServiceID,
			module,
			pythonStringListLiteral(serviceCapabilities),
		))
	}
	return strings.Join([]string{
		"import importlib",
		"",
		"import pytest",
		"from fastapi.testclient import TestClient",
		"",
		"from " + packageName + ".runtime_target import GENERATED_CAPABILITY_METADATA",
		"",
		"SERVICE_MODULES = [",
		strings.Join(serviceModules, "\n"),
		"]",
		"",
		"def _capability_map(payload: dict) -> dict:",
		"    capabilities = payload.get('capabilities')",
		"    if capabilities is None and isinstance(payload.get('anip_discovery'), dict):",
		"        capabilities = payload['anip_discovery'].get('capabilities', {})",
		"    if isinstance(capabilities, list):",
		"        return {item.get('name'): item for item in capabilities if isinstance(item, dict) and item.get('name')}",
		"    if isinstance(capabilities, dict):",
		"        return capabilities",
		"    return {}",
		"",
		"def _issue_token(client: TestClient, capability_id: str, scope: list[str]) -> str:",
		"    response = client.post(",
		`        "/anip/tokens",`,
		`        headers={"Authorization": "Bearer dev-admin-key"},`,
		`        json={`,
		`            "capability": capability_id,`,
		`            "scope": scope,`,
		`            "subject": "agent:test",`,
		`            "purpose_parameters": {"actor_id": "test", "source": "pytest"},`,
		`        },`,
		"    )",
		"    assert response.status_code == 200",
		`    return response.json()["token"]`,
		"",
		"def _minimum_scope(client: TestClient, capability_id: str, fallback: list[str]) -> list[str]:",
		"    manifest = client.get('/anip/manifest')",
		"    assert manifest.status_code == 200",
		"    capabilities = _capability_map(manifest.json())",
		"    capability = capabilities.get(capability_id, {})",
		"    return capability.get('minimum_scope') or fallback",
		"",
		"@pytest.mark.parametrize('service', SERVICE_MODULES)",
		"def test_generated_service_discovery_and_invoke(service: dict[str, object]) -> None:",
		"    module = importlib.import_module(str(service['module']))",
		"    client = TestClient(module.create_app())",
		"    discovery = client.get('/.well-known/anip')",
		"    assert discovery.status_code == 200",
		"    discovery_names = set(_capability_map(discovery.json()).keys())",
		"    assert discovery_names == set(service['capabilities'])",
		"",
		"    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item['capability_id'] == service['capabilities'][0])",
		"    token = _issue_token(client, capability['capability_id'], _minimum_scope(client, capability['capability_id'], capability['minimum_scope']))",
		"    invoke = client.post(",
		`        f"/anip/invoke/{capability['capability_id']}",`,
		`        headers={"Authorization": f"Bearer {token}"},`,
		`        json={"parameters": capability["sample_parameters"]},`,
		"    )",
		"    assert invoke.status_code == 200",
		"    payload = invoke.json()",
		`    assert payload["success"] is True`,
		`    assert payload["result"]["execution_status"]`,
		"",
	}, "\n")
}

func localPythonDependencyPath(packageDir string) string {
	_, currentFile, _, _ := runtime.Caller(0)
	root := filepath.Clean(filepath.Join(filepath.Dir(currentFile), "..", "..", ".."))
	return filepath.ToSlash(filepath.Join(root, "packages", "python", packageDir))
}

func pythonModuleName(systemName string) string {
	name := systemNameToPackageName(systemName)
	name = strings.ReplaceAll(name, "-", "_")
	if name == "" {
		return "generated_anip_service"
	}
	return name
}

func PythonModuleNameForPackageID(packageID string) string {
	return pythonModuleName(packageID)
}

func pythonStringListLiteral(values []string) string {
	if len(values) == 0 {
		return "[]"
	}
	quoted := make([]string, 0, len(values))
	for _, value := range values {
		quoted = append(quoted, fmt.Sprintf("%q", value))
	}
	return "[" + strings.Join(quoted, ", ") + "]"
}
