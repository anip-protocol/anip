using Anip.Core;
using Anip.Service;
using System.Linq;
using System.Text.Json;

namespace notiongovernedfrontingshowcase;

public static class GeneratedCapabilities
{

    public static List<CapabilityDef> CreateAll(BackendAdapterHandler backendAdapter)
    {
        return CreateAll(backendAdapter, "");
    }

    public static List<CapabilityDef> CreateAll(BackendAdapterHandler backendAdapter, string? serviceFilter)
    {
        var normalizedServiceFilter = serviceFilter?.Trim() ?? "";
        return GeneratedRuntimeTarget.Capabilities
            .Where(capability => string.IsNullOrWhiteSpace(normalizedServiceFilter) || normalizedServiceFilter == StringValue(capability, "service_id"))
            .Select(capability => CreateCapability(capability, backendAdapter))
            .ToList();
    }

    private static CapabilityDef CreateCapability(
        Dictionary<string, object?> capability,
        BackendAdapterHandler backendAdapter)
    {
        var declaration = new CapabilityDeclaration
        {
            Name = StringValue(capability, "capability_id"),
            Description = FirstNonEmpty(StringValue(capability, "summary"), StringValue(capability, "title"), StringValue(capability, "capability_id")) ?? string.Empty,
            ContractVersion = GeneratedRuntimeTarget.ContractVersion,
            Inputs = BuildInputs(capability),
            Output = new CapabilityOutput
            {
                Type = FirstNonEmpty(StringValue(capability, "output_shape"), "governed_result") ?? "governed_result",
                Fields = ["execution_status", "capability_id", "semantic_input", "backend_input_contract", "note"],
            },
            SideEffect = new SideEffect
            {
                Type = SideEffectType(StringValue(capability, "side_effect_level")),
                RollbackWindow = RollbackWindowFor(StringValue(capability, "side_effect_level")),
            },
            MinimumScope = StringList(capability.GetValueOrDefault("minimum_scope")),
            ResponseModes = ["unary"],
            RefreshVia = [],
            VerifyVia = [],
            Kind = DeclarationKind(capability),
            Composition = DeclarationComposition(capability),
            GrantPolicy = DeserializeModel<GrantPolicy>(capability.GetValueOrDefault("grant_policy")),
        };

        return new CapabilityDef(declaration, (ctx, parameters) =>
            Handle(capability, ctx, parameters, backendAdapter));
    }

    private static T? DeserializeModel<T>(object? value)
    {
        if (value is null) return default;
        return JsonSerializer.Deserialize<T>(JsonSerializer.Serialize(value));
    }

    private static string DeclarationKind(Dictionary<string, object?> capability)
    {
        var kind = FirstNonEmpty(StringValue(capability, "kind"), "atomic")!;
        return kind;
    }

    private static Composition? DeclarationComposition(Dictionary<string, object?> capability)
    {
        return DeserializeModel<Composition>(capability.GetValueOrDefault("composition"));
    }

    private static Dictionary<string, object?> Handle(
        Dictionary<string, object?> capability,
        InvocationContext ctx,
        Dictionary<string, object?> parameters,
        BackendAdapterHandler backendAdapter)
    {
        parameters = ApplyInputDefaults(capability, parameters);
        AssertRequiredSemanticInputs(capability, parameters);
        ValidateInputBehavior(capability, parameters);
        var policy = Policy.Evaluate(capability, parameters, ctx.RootPrincipal);
        if (policy.Decision == "deny")
        {
            throw new AnipError("denied", FirstNonEmpty(policy.Detail, $"Request denied for {StringValue(capability, "capability_id")}.")!).WithResolution("contact_service_owner");
        }
        if (policy.Decision == "clarify")
        {
            throw new AnipError("clarification_required", FirstNonEmpty(policy.Detail, $"Clarification required for {StringValue(capability, "capability_id")}.")!).WithResolution("obtain_binding");
        }

        var plan = BuildBackendInvocationPlan(capability, parameters);
        if (policy.Decision == "approval_required" && string.IsNullOrWhiteSpace(ctx.ApprovalGrant))
        {
            throw new AnipError("approval_required", FirstNonEmpty(policy.Detail, $"Approval required for {StringValue(capability, "capability_id")}.")!).WithResolution("request_approval");
        }
        return backendAdapter(capability, plan, (Dictionary<string, object?>)plan["adapter_input"]!, ctx);
    }

    private static List<CapabilityInput> BuildInputs(Dictionary<string, object?> capability)
    {
        var inputs = new List<CapabilityInput>();
        foreach (var input in InputList(capability, "required_inputs"))
        {
            inputs.Add(new CapabilityInput
            {
                Name = StringValue(input, "input_name"),
                Type = FirstNonEmpty(StringValue(input, "input_type"), "string")!,
                Required = true,
                Default = DefaultValue(input),
                Description = FirstNonEmpty(StringValue(input, "summary"), StringValue(input, "input_name")),
                SemanticType = OptionalString(input, "semantic_type"),
                EntityReference = BoolValue(input.GetValueOrDefault("entity_reference")),
                AllowedValues = StringList(input.GetValueOrDefault("allowed_values")),
                CatalogRef = OptionalString(input, "catalog_ref"),
                InputMeanings = DeserializeModel<List<InputMeaning>>(input.GetValueOrDefault("input_meanings")) ?? [],
                Resolution = DeserializeModel<InputResolution>(input.GetValueOrDefault("resolution")),
            });
        }
        foreach (var input in InputList(capability, "optional_inputs"))
        {
            inputs.Add(new CapabilityInput
            {
                Name = StringValue(input, "input_name"),
                Type = FirstNonEmpty(StringValue(input, "input_type"), "string")!,
                Required = false,
                Default = DefaultValue(input),
                Description = FirstNonEmpty(StringValue(input, "summary"), StringValue(input, "input_name")),
                SemanticType = OptionalString(input, "semantic_type"),
                EntityReference = BoolValue(input.GetValueOrDefault("entity_reference")),
                AllowedValues = StringList(input.GetValueOrDefault("allowed_values")),
                CatalogRef = OptionalString(input, "catalog_ref"),
                InputMeanings = DeserializeModel<List<InputMeaning>>(input.GetValueOrDefault("input_meanings")) ?? [],
                Resolution = DeserializeModel<InputResolution>(input.GetValueOrDefault("resolution")),
            });
        }
        return inputs;
    }

    private static void AssertRequiredSemanticInputs(
        Dictionary<string, object?> capability,
        Dictionary<string, object?> parameters)
    {
        var missing = new List<string>();
        foreach (var input in InputList(capability, "required_inputs"))
        {
            if (!string.IsNullOrWhiteSpace(StringValue(input, "default_value"))) continue;
            var inputName = StringValue(input, "input_name");
            if (!parameters.TryGetValue(inputName, out var value) || value is null || value is string text && string.IsNullOrWhiteSpace(text))
            {
                missing.Add(inputName);
            }
        }
        if (missing.Count > 0)
        {
            throw new AnipError("clarification_required", $"Required semantic inputs are missing for {StringValue(capability, "capability_id")}.", new Resolution
            {
                Action = "obtain_binding",
                RecoveryClass = Constants.RecoveryClassForAction("obtain_binding"),
                Requires = string.Join(",", missing),
            });
        }
    }

    private static void ValidateInputBehavior(
        Dictionary<string, object?> capability,
        Dictionary<string, object?> parameters)
    {
        foreach (var input in InputList(capability, "required_inputs").Concat(InputList(capability, "optional_inputs")))
        {
            var inputName = StringValue(input, "input_name");
            if (string.IsNullOrWhiteSpace(inputName)) continue;
            if (!parameters.TryGetValue(inputName, out var value) || value is null || value is string text && string.IsNullOrWhiteSpace(text)) continue;
            var allowedValues = StringList(input.GetValueOrDefault("allowed_values"));
            if (allowedValues.Count == 0 || allowedValues.Contains(value.ToString() ?? string.Empty)) continue;
            var resolution = DictionaryValue(input.GetValueOrDefault("resolution"));
            var shouldDeny = StringValue(resolution, "mode") == "closed_values" && StringValue(resolution, "on_unresolved") == "deny";
            var action = shouldDeny ? "contact_service_owner" : "obtain_binding";
            throw new AnipError(shouldDeny ? "denied" : "clarification_required", $"Input {inputName} must use one of the declared allowed values.", new Resolution
            {
                Action = action,
                RecoveryClass = Constants.RecoveryClassForAction(action),
                Requires = inputName,
            });
        }
    }

    private static object? DefaultValue(Dictionary<string, object?> input)
    {
        var value = StringValue(input, "default_value");
        return string.IsNullOrWhiteSpace(value) ? null : value;
    }

    private static Dictionary<string, object?> ApplyInputDefaults(Dictionary<string, object?> capability, Dictionary<string, object?> parameters)
    {
        var normalized = new Dictionary<string, object?>(parameters);
        foreach (var input in InputList(capability, "required_inputs").Concat(InputList(capability, "optional_inputs")))
        {
            var inputName = StringValue(input, "input_name");
            var defaultValue = StringValue(input, "default_value");
            var resolution = DictionaryValue(input.GetValueOrDefault("resolution"));
            if (StringValue(resolution, "on_missing") == "omit") continue;
            if (string.IsNullOrWhiteSpace(inputName) || string.IsNullOrWhiteSpace(defaultValue)) continue;
            if (!normalized.TryGetValue(inputName, out var value) || value is null || value is string text && string.IsNullOrWhiteSpace(text))
            {
                normalized[inputName] = defaultValue;
            }
        }
        return normalized;
    }

    private static Dictionary<string, object?> BuildBackendInvocationPlan(
        Dictionary<string, object?> capability,
        Dictionary<string, object?> parameters)
    {
        var selectedBinding = SelectBackendBinding(capability);
        var contract = EffectiveBackendInputContract(capability, selectedBinding);
        var semanticKeys = new HashSet<string>();
        foreach (var input in InputList(capability, "required_inputs")) semanticKeys.Add(StringValue(input, "input_name"));
        foreach (var input in InputList(capability, "optional_inputs")) semanticKeys.Add(StringValue(input, "input_name"));

        var semanticInput = new Dictionary<string, object?>();
        foreach (var entry in parameters)
        {
            if (semanticKeys.Contains(entry.Key))
            {
                semanticInput[entry.Key] = entry.Value;
            }
        }

        var adapterKeys = new HashSet<string>(semanticKeys);
        foreach (var required in StringList(contract.GetValueOrDefault("required"))) adapterKeys.Add(required);
        foreach (var optional in StringList(contract.GetValueOrDefault("optional"))) adapterKeys.Add(optional);
        var adapterInput = new Dictionary<string, object?>();
        foreach (var entry in parameters)
        {
            if (adapterKeys.Contains(entry.Key))
            {
                adapterInput[entry.Key] = entry.Value;
            }
        }

        var unresolved = new List<string>();
        foreach (var required in StringList(contract.GetValueOrDefault("required")))
        {
            if (!parameters.TryGetValue(required, out var value) || value is null)
            {
                unresolved.Add(required);
            }
        }

        return new Dictionary<string, object?>
        {
            ["selected_binding"] = selectedBinding,
            ["semantic_input"] = semanticInput,
            ["adapter_input"] = adapterInput,
            ["backend_input_contract"] = contract,
            ["unresolved_required_backend_inputs"] = unresolved,
        };
    }

    private static Dictionary<string, object?>? SelectBackendBinding(Dictionary<string, object?> capability)
    {
        var bindings = MapList(capability.GetValueOrDefault("backend_bindings"));
        return bindings.Count == 0 ? null : bindings[0];
    }

    private static Dictionary<string, object?> EffectiveBackendInputContract(
        Dictionary<string, object?> capability,
        Dictionary<string, object?>? selectedBinding)
    {
        var mode = FirstNonEmpty(StringValue(selectedBinding, "backend_input_mode"), StringValue(capability, "backend_input_mode"), "implicit")!;
        var derivedRequired = FirstNonEmptyList(StringList(selectedBinding?.GetValueOrDefault("derived_required_backend_inputs")), StringList(capability.GetValueOrDefault("derived_required_backend_inputs")));
        var derivedOptional = FirstNonEmptyList(StringList(selectedBinding?.GetValueOrDefault("derived_optional_backend_inputs")), StringList(capability.GetValueOrDefault("derived_optional_backend_inputs")));
        var explicitRequired = FirstNonEmptyList(StringList(selectedBinding?.GetValueOrDefault("explicit_required_backend_inputs")), StringList(capability.GetValueOrDefault("explicit_required_backend_inputs")));
        var explicitOptional = FirstNonEmptyList(StringList(selectedBinding?.GetValueOrDefault("explicit_optional_backend_inputs")), StringList(capability.GetValueOrDefault("explicit_optional_backend_inputs")));

        if (mode == "explicit")
        {
            var required = UniqueStrings(explicitRequired);
            return new Dictionary<string, object?>
            {
                ["mode"] = "explicit",
                ["required"] = required,
                ["optional"] = Exclude(UniqueStrings(explicitOptional), required),
            };
        }
        if (mode == "hybrid")
        {
            var required = UniqueStrings([..derivedRequired, ..explicitRequired]);
            return new Dictionary<string, object?>
            {
                ["mode"] = "hybrid",
                ["required"] = required,
                ["optional"] = Exclude(UniqueStrings([..derivedOptional, ..explicitOptional]), required),
            };
        }

        var implicitRequired = UniqueStrings(derivedRequired);
        return new Dictionary<string, object?>
        {
            ["mode"] = "implicit",
            ["required"] = implicitRequired,
            ["optional"] = Exclude(UniqueStrings(derivedOptional), implicitRequired),
        };
    }

    public static List<string> StringList(object? value)
    {
        if (value is List<string> strings) return strings;
        if (value is IEnumerable<object?> objects) return objects.Where(item => item is not null).Select(item => item!.ToString()!).ToList();
        if (value is JsonElement { ValueKind: JsonValueKind.Array } array)
        {
            return array.EnumerateArray().Select(item => item.ValueKind == JsonValueKind.String ? item.GetString() ?? string.Empty : item.ToString()).Where(item => !string.IsNullOrWhiteSpace(item)).ToList();
        }
        return [];
    }

    private static List<Dictionary<string, object?>> InputList(Dictionary<string, object?> capability, string key)
    {
        return MapList(capability.GetValueOrDefault(key));
    }

    private static List<Dictionary<string, object?>> MapList(object? value)
    {
        if (value is List<Dictionary<string, object?>> dictionaries) return dictionaries;
        if (value is JsonElement { ValueKind: JsonValueKind.Array } array)
        {
            var result = new List<Dictionary<string, object?>>();
            foreach (var item in array.EnumerateArray())
            {
                if (item.ValueKind != JsonValueKind.Object) continue;
                var map = JsonSerializer.Deserialize<Dictionary<string, object?>>(item.GetRawText());
                if (map is not null) result.Add(map);
            }
            return result;
        }
        return [];
    }

    private static List<string> GovernanceList(Dictionary<string, object?> capability, string key)
    {
        if (capability.TryGetValue("governance", out var governance) && governance is Dictionary<string, object?> governanceMap)
        {
            return StringList(governanceMap.GetValueOrDefault(key));
        }
        if (capability.TryGetValue("governance", out governance) && governance is JsonElement { ValueKind: JsonValueKind.Object } governanceElement && governanceElement.TryGetProperty(key, out var property) )
        {
            return StringList(property);
        }
        return [];
    }

    private static string StringValue(Dictionary<string, object?>? values, string key)
    {
        if (values is null) return string.Empty;
        return values.TryGetValue(key, out var value) && value is not null ? value.ToString() ?? string.Empty : string.Empty;
    }

    private static Dictionary<string, object?> DictionaryValue(object? value)
    {
        if (value is Dictionary<string, object?> dictionary) return dictionary;
        if (value is JsonElement { ValueKind: JsonValueKind.Object } element)
        {
            return JsonSerializer.Deserialize<Dictionary<string, object?>>(element.GetRawText()) ?? [];
        }
        return [];
    }

    private static string? OptionalString(Dictionary<string, object?>? values, string key)
    {
        var value = StringValue(values, key);
        return string.IsNullOrWhiteSpace(value) ? null : value;
    }

    private static bool BoolValue(object? value)
    {
        if (value is bool flag) return flag;
        if (value is string text && bool.TryParse(text, out var parsed)) return parsed;
        if (value is JsonElement { ValueKind: JsonValueKind.True }) return true;
        if (value is JsonElement { ValueKind: JsonValueKind.False }) return false;
        return false;
    }

    private static string? FirstNonEmpty(params string?[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value)) return value;
        }
        return null;
    }

    private static List<string> FirstNonEmptyList(List<string> primary, List<string> fallback)
    {
        return primary.Count > 0 ? primary : fallback;
    }

    private static List<string> UniqueStrings(IEnumerable<string> values)
    {
        var result = new List<string>();
        foreach (var value in values)
        {
            if (string.IsNullOrWhiteSpace(value) || result.Contains(value)) continue;
            result.Add(value);
        }
        return result;
    }

    private static List<string> Exclude(List<string> values, List<string> excluded)
    {
        return values.Where(value => !excluded.Contains(value)).ToList();
    }

    private static string SideEffectType(string sideEffectLevel)
    {
        var normalized = sideEffectLevel.ToLowerInvariant();
        if (normalized.Contains("irreversible")) return "irreversible";
        if (normalized.Contains("transaction")) return "transactional";
        if (normalized.Contains("write")) return "write";
        return "read";
    }

    private static string RollbackWindowFor(string sideEffectLevel)
    {
        return SideEffectType(sideEffectLevel) switch
        {
            "read" => "not_applicable",
            "irreversible" => "none",
            _ => "PT15M",
        };
    }
}
