using System.Text.Json;
using System.Text.Json.Serialization;

namespace notiongovernedfrontingshowcase;

public readonly record struct PolicyDecision(string Decision, string? Detail);

public sealed class PrincipalSelector
{
    [JsonPropertyName("claim")] public string? Claim { get; set; }
    [JsonPropertyName("equals")] public string? EqualsValue { get; set; }
}

public sealed class RuntimePolicyBinding
{
    [JsonPropertyName("id")] public string? Id { get; set; }
    [JsonPropertyName("actor_id")] public string? ActorId { get; set; }
    [JsonPropertyName("principal_selector")] public PrincipalSelector? PrincipalSelector { get; set; }
    [JsonPropertyName("capability_ids")] public List<string>? CapabilityIds { get; set; }
    [JsonPropertyName("decision")] public string? Decision { get; set; }
    [JsonPropertyName("business_rule")] public string? BusinessRule { get; set; }
    [JsonPropertyName("enforcement_notes")] public string? EnforcementNotes { get; set; }
}

public sealed class RuntimePolicyTarget
{
    [JsonPropertyName("policy_bindings")] public List<RuntimePolicyBinding>? PolicyBindings { get; set; }
}

public static class Policy
{
    private static readonly List<RuntimePolicyBinding> PolicyBindings =
        JsonSerializer.Deserialize<RuntimePolicyTarget>(GeneratedRuntimeTarget.RuntimeTargetJson)?.PolicyBindings ?? [];

    public static PolicyDecision Evaluate(
        Dictionary<string, object?> capability,
        Dictionary<string, object?> parameters,
        string? rootPrincipal)
    {
        var capabilityId = StringValue(capability, "capability_id");
        var bindings = PolicyBindings.Where(binding => binding.CapabilityIds?.Contains(capabilityId) == true).ToList();
        if (bindings.Count == 0) return new PolicyDecision("allow", null);
        var claims = PrincipalClaims(rootPrincipal);
        if (claims.Count == 0) return new PolicyDecision("allow", null);
        var matching = bindings.Where(binding => MatchesPrincipal(binding, claims)).ToList();
        if (RequiresGovernedStop(capability))
        {
            var denied = matching.FirstOrDefault(binding => binding.Decision == "deny");
            if (denied is not null) return DecisionFor(denied);
            var approval = matching.FirstOrDefault(binding => binding.Decision == "approval_required");
            if (approval is not null) return DecisionFor(approval);
            var clarify = matching.FirstOrDefault(binding => binding.Decision == "clarify");
            if (clarify is not null) return DecisionFor(clarify);
        }
        var allowed = matching.FirstOrDefault(binding => binding.Decision != "deny" && binding.Decision != "clarify" && binding.Decision != "approval_required");
        if (allowed is not null) return DecisionFor(allowed);
        return new PolicyDecision("allow", "No matching runtime policy binding; continuing.");
    }

    private static bool RequiresGovernedStop(Dictionary<string, object?> capability)
    {
        return capability.GetValueOrDefault("grant_policy") is JsonElement { ValueKind: JsonValueKind.Object } grantPolicy && grantPolicy.EnumerateObject().Any()
            || StringValue(capability, "side_effect_level") == "approval_required"
            || StringValue(capability, "execution_posture") == "approval_required"
            || StringValue(capability, "operation_type") == "approval_gated";
    }

    private static PolicyDecision DecisionFor(RuntimePolicyBinding binding)
    {
        var decision = FirstNonEmpty(binding.Decision, "allow")!;
        var detail = FirstNonEmpty(binding.BusinessRule, binding.EnforcementNotes);
        if (decision == "deny" || decision == "clarify" || decision == "approval_required")
        {
            return new PolicyDecision(decision, detail);
        }
        return new PolicyDecision("allow", detail);
    }

    private static Dictionary<string, string> PrincipalClaims(string? rootPrincipal)
    {
        var raw = rootPrincipal?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(raw)) return [];
        var pieces = raw.Split('|');
        var claims = new Dictionary<string, string> { ["principal"] = pieces.Length > 0 ? pieces[0] : string.Empty };
        foreach (var piece in pieces.Skip(1))
        {
            var separator = piece.IndexOf('=');
            if (separator < 0) continue;
            claims[piece[..separator].Trim()] = piece[(separator + 1)..].Trim();
        }
        return claims;
    }

    private static bool MatchesPrincipal(RuntimePolicyBinding binding, Dictionary<string, string> claims)
    {
        var claim = FirstNonEmpty(binding.PrincipalSelector?.Claim, "actor_id")!;
        var expected = FirstNonEmpty(binding.PrincipalSelector?.EqualsValue, binding.ActorId);
        if (string.IsNullOrWhiteSpace(expected)) return true;
        if (!claims.ContainsKey(claim)) return false;
        return claims.TryGetValue(claim, out var actual) && actual == expected;
    }

    private static string StringValue(Dictionary<string, object?> values, string key)
    {
        return values.TryGetValue(key, out var value) && value is not null ? value.ToString() ?? string.Empty : string.Empty;
    }

    private static string? FirstNonEmpty(params string?[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value)) return value;
        }
        return null;
    }
}
