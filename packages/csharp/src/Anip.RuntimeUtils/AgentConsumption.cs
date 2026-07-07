using System.Collections;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Anip.RuntimeUtils;

/// <summary>
/// Provides deterministic, contract-derived helpers for consuming agents.
/// </summary>
public static partial class AgentConsumption
{
    /// <summary>
    /// Options for deterministic planner fallback validation.
    /// </summary>
    /// <param name="CompactCandidateIds">Optional compact candidate capability identifiers that the planner was allowed to choose from.</param>
    public sealed record FallbackValidationOptions(IReadOnlyList<string>? CompactCandidateIds = null);

    private static readonly IReadOnlyDictionary<string, IReadOnlySet<string>> EffectTerms =
        new Dictionary<string, IReadOnlySet<string>>(StringComparer.Ordinal)
        {
            ["approval.execute"] = new HashSet<string>(["approve", "apply", "commit", "execute", "perform"], StringComparer.Ordinal),
            ["external_dispatch"] = new HashSet<string>(["deliver", "dispatch", "publish", "send", "ship"], StringComparer.Ordinal),
            ["raw_data_export"] = new HashSet<string>(["csv", "download", "dump", "export", "raw", "spreadsheet"], StringComparer.Ordinal),
            ["system.mutation"] = new HashSet<string>(["apply", "commit", "delete", "mutate", "update"], StringComparer.Ordinal)
        };

    private static readonly IReadOnlySet<string> NegationTerms =
        new HashSet<string>(["avoid", "exclude", "no", "not", "without"], StringComparer.Ordinal);

    private static readonly IReadOnlySet<string> CapabilityScoringStopTokens =
        new HashSet<string>(
            ["after", "and", "before", "for", "in", "of", "that", "the", "these", "this", "those", "to", "with"],
            StringComparer.Ordinal);

    private static readonly IReadOnlySet<string> WeakInputTokens =
        new HashSet<string>(["id", "ids", "input", "name", "names", "ref", "reference", "value", "values"], StringComparer.Ordinal);

    /// <summary>
    /// Normalizes text for compact semantic substring checks.
    /// </summary>
    /// <param name="value">The value to normalize.</param>
    /// <returns>Lowercase alphanumeric text with separators removed.</returns>
    public static string SemanticTextKey(object? value)
    {
        return SemanticTextRegex().Replace(StringValue(value).ToLowerInvariant(), string.Empty);
    }

    /// <summary>
    /// Returns normalized alphanumeric tokens from a value.
    /// </summary>
    /// <param name="value">The value to tokenize.</param>
    /// <returns>Unique lowercase tokens in first-seen order.</returns>
    public static IReadOnlySet<string> TextTokens(object? value)
    {
        return OrderedTextTokens(value).ToHashSet(StringComparer.Ordinal);
    }

    /// <summary>
    /// Returns required input names that are not grounded by the conversation.
    /// </summary>
    /// <param name="conversation">The user conversation or request text.</param>
    /// <param name="metadata">Contract-derived metadata for one capability.</param>
    /// <returns>Required input names that should be clarified before invocation.</returns>
    public static IReadOnlyList<string> MissingRequiredInputNames(string conversation, object? metadata)
    {
        var safeMetadata = MapValue(metadata);
        var missing = new List<string>();
        foreach (var rawSpec in ListValue(GetValue(safeMetadata, "input_specs")))
        {
            var spec = MapValue(rawSpec);
            if (!BoolValue(GetValue(spec, "required")))
            {
                continue;
            }

            var name = StringValue(GetValue(spec, "name"));
            if (name.Length == 0)
            {
                continue;
            }

            if (InputHasDefault(spec) && StringValue(GetValue(MapValue(GetValue(spec, "resolution")), "on_missing")) == "use_default")
            {
                continue;
            }

            if (!InputGrounded(conversation, InputCandidateValues(safeMetadata, spec)))
            {
                missing.Add(name);
            }
        }

        return missing;
    }

    /// <summary>
    /// Returns declared unsupported effects requested by the conversation.
    /// </summary>
    /// <param name="conversation">The user conversation or request text.</param>
    /// <param name="metadata">Contract-derived metadata for one capability.</param>
    /// <returns>Unsupported effect identifiers requested by the conversation.</returns>
    public static IReadOnlyList<string> RequestedUnsupportedEffects(string conversation, object? metadata)
    {
        var safeMetadata = MapValue(metadata);
        var tokens = TextTokens(conversation);
        var orderedTokens = OrderedTextTokens(conversation);
        var blocked = CapabilityDoesNotProduce(safeMetadata);
        var produced = CapabilityProduces(safeMetadata);
        var boundaries = AppBoundaries(safeMetadata);
        var lowered = conversation.ToLowerInvariant();
        var requested = new HashSet<string>(StringComparer.Ordinal);

        foreach (var (effect, rawTerms) in MapValue(GetValue(boundaries, "unsupported_terms")))
        {
            foreach (var term in StringList(rawTerms))
            {
                if (term.Length > 0 && lowered.Contains(term.ToLowerInvariant(), StringComparison.Ordinal))
                {
                    requested.Add(effect);
                }
            }
        }

        foreach (var (effect, terms) in EffectTerms)
        {
            var matchedTerms = terms.Where(tokens.Contains).ToArray();
            if (matchedTerms.Length == 0)
            {
                continue;
            }

            var allNegated = matchedTerms.All(term => TermIsNegated(orderedTokens, term));
            if (!allNegated
                && (blocked.Contains(effect)
                    || (effect == "raw_data_export" && !produced.Contains("raw_data_export"))
                    || (effect == "external_dispatch" && produced.Contains("content.draft"))))
            {
                requested.Add(effect);
            }
        }

        return requested.Order(StringComparer.Ordinal).ToArray();
    }

    /// <summary>
    /// Alias for <see cref="RequestedUnsupportedEffects"/>.
    /// </summary>
    /// <param name="conversation">The user conversation or request text.</param>
    /// <param name="metadata">Contract-derived metadata for one capability.</param>
    /// <returns>Unsupported effect identifiers requested by the conversation.</returns>
    public static IReadOnlyList<string> DetectUnsupportedEffects(string conversation, object? metadata)
    {
        return RequestedUnsupportedEffects(conversation, metadata);
    }

    /// <summary>
    /// Scores how well a capability's declared metadata matches conversation text.
    /// </summary>
    /// <param name="conversation">The user conversation or request text.</param>
    /// <param name="capabilityId">The capability identifier being scored.</param>
    /// <param name="metadata">Contract-derived metadata for one capability.</param>
    /// <returns>A deterministic match score in which higher values are stronger matches.</returns>
    public static double CapabilityMatchScore(string conversation, string capabilityId, object? metadata)
    {
        var safeMetadata = MapValue(metadata);
        var inputFragments = new List<string>();
        foreach (var rawSpec in ListValue(GetValue(safeMetadata, "input_specs")))
        {
            var spec = MapValue(rawSpec);
            inputFragments.Add(StringValue(GetValue(spec, "name")));
            inputFragments.Add(StringValue(GetValue(spec, "semantic_type")));
            inputFragments.Add(StringValue(GetValue(spec, "description")));
            inputFragments.AddRange(StringList(GetValue(spec, "allowed_values")));
        }

        var appProfile = MapValue(GetValue(safeMetadata, "app_profile"));
        var intent = MapValue(GetValue(appProfile, "intent"));
        var haystack = string.Join(
            " ",
            [
                capabilityId,
                StringValue(GetValue(safeMetadata, "capability_id")),
                StringValue(GetValue(safeMetadata, "id")),
                StringValue(GetValue(safeMetadata, "description")),
                StringValue(GetValue(safeMetadata, "capability_framing")),
                StringValue(GetValue(safeMetadata, "summary")),
                StringValue(GetValue(safeMetadata, "output_intent")),
                StringValue(GetValue(appProfile, "capability_framing")),
                StringValue(GetValue(intent, "category")),
                StringValue(GetValue(intent, "summary")),
                StringValue(GetValue(appProfile, "input_meanings")),
                StringValue(GetValue(appProfile, "app_boundaries")),
                string.Join(" ", inputFragments)
            ]);

        var sourceTokens = ScoreTokens(conversation);
        var targetTokens = ScoreTokens(haystack);
        if (sourceTokens.Count == 0 || targetTokens.Count == 0)
        {
            return 0.0;
        }

        var overlap = Overlap(sourceTokens, targetTokens);
        var recall = (double)overlap / sourceTokens.Count;
        var precision = (double)overlap / targetTokens.Count;

        var idTokens = ScoreTokens(capabilityId);
        var idPrecision = idTokens.Count == 0 ? 0.0 : (double)Overlap(sourceTokens, idTokens) / idTokens.Count;
        return recall * 0.65 + precision * 0.25 + idPrecision * 0.1;
    }

    /// <summary>
    /// Selects the strongest same-effect capability from available metadata.
    /// </summary>
    /// <param name="conversation">The user conversation or request text.</param>
    /// <param name="selectedCapability">The capability selected by the caller or planner.</param>
    /// <param name="metadata">Capability metadata keyed by capability identifier.</param>
    /// <returns>The selected capability or a stronger same-effect capability.</returns>
    public static string SelectConsumableCapability(string conversation, string selectedCapability, object? metadata)
    {
        var metadataByCapability = MapValue(metadata);
        if (!metadataByCapability.TryGetValue(selectedCapability, out var rawSelectedMetadata))
        {
            return selectedCapability;
        }

        var selectedMetadata = MapValue(rawSelectedMetadata);
        var selectedMissing = MissingRequiredInputNames(conversation, selectedMetadata);
        var selectedScore = CapabilityMatchScore(conversation, selectedCapability, selectedMetadata);
        var bestCapability = selectedCapability;
        var bestScore = selectedScore;

        foreach (var (capabilityId, rawCandidate) in metadataByCapability)
        {
            var candidate = MapValue(rawCandidate);
            if (capabilityId == selectedCapability || !SameEffectClass(selectedMetadata, candidate))
            {
                continue;
            }

            var missing = MissingRequiredInputNames(conversation, candidate);
            if (selectedMissing.Count > 0 && missing.Count > 0 && !MissingRequiredInputsAreReferenced(conversation, candidate, missing))
            {
                continue;
            }

            var score = CapabilityMatchScore(conversation, capabilityId, candidate);
            if (score > bestScore)
            {
                bestCapability = capabilityId;
                bestScore = score;
            }
        }

        return bestCapability != selectedCapability && bestScore >= Math.Max(0.12, selectedScore + 0.08)
            ? bestCapability
            : selectedCapability;
    }

    /// <summary>
    /// Returns the primary content effect requested by the conversation, when detectable.
    /// </summary>
    /// <param name="conversation">The user conversation or request text.</param>
    /// <returns>The requested content effect identifier, or null.</returns>
    public static string? RequestedPrimaryContentEffect(string conversation)
    {
        var tokens = TextTokens(conversation);
        var orderedTokens = OrderedTextTokens(conversation);
        if (HasUnnegatedToken(tokens, orderedTokens, ["recommend", "recommendation", "recommendations"]))
        {
            return "content.recommendation";
        }

        if (HasUnnegatedToken(tokens, orderedTokens, ["draft", "email", "outreach", "message", "variant", "variants", "option", "options"]))
        {
            return "content.draft";
        }

        return HasUnnegatedToken(tokens, orderedTokens, ["summarize", "summary"]) ? "content.summary" : null;
    }

    /// <summary>
    /// Reports whether a capability is an approval boundary.
    /// </summary>
    /// <param name="metadata">Contract-derived metadata for one capability.</param>
    /// <returns>True when the capability produces approval or preview effects, or declares approval as required.</returns>
    public static bool IsApprovalCapability(object? metadata)
    {
        var safeMetadata = MapValue(metadata);
        var produced = CapabilityProduces(safeMetadata);
        return produced.Contains("approval.request")
            || produced.Contains("system.preview_mutation")
            || BoolValue(GetValue(MapValue(GetValue(safeMetadata, "approval")), "required"));
    }

    /// <summary>
    /// Returns deterministic reasons a primary planner result should escalate to a fallback model.
    /// </summary>
    /// <param name="plan">The planner result to validate.</param>
    /// <param name="conversation">The user conversation or request text.</param>
    /// <param name="metadata">Capability metadata keyed by capability identifier.</param>
    /// <param name="options">Optional fallback validation settings.</param>
    /// <returns>Fallback reasons. An empty list means the plan can proceed to service-side enforcement.</returns>
    public static IReadOnlyList<string> ValidateInvocationPlanForFallback(
        object? plan,
        string conversation,
        object? metadata,
        FallbackValidationOptions? options = null)
    {
        var reasons = new List<string>();
        var safePlan = MapValue(plan);
        var capability = StringValue(GetValue(safePlan, "selected_capability"));
        if (capability.Length == 0)
        {
            return ["selected capability is missing"];
        }

        var metadataByCapability = MapValue(metadata);
        var capabilityMetadata = MapValue(GetValue(metadataByCapability, capability));
        if (capabilityMetadata.Count == 0)
        {
            return [$"selected capability is not discovered: {capability}"];
        }

        var compactCandidateIds = options?.CompactCandidateIds ?? [];
        if (compactCandidateIds.Count > 0 && !compactCandidateIds.Contains(capability))
        {
            reasons.Add($"selected capability is outside compact candidate set: {capability}");
        }

        var parameters = MapValue(GetValue(safePlan, "parameters"));
        if (!IsObjectValue(GetValue(safePlan, "parameters")))
        {
            reasons.Add("parameters payload is not an object");
            parameters = new Dictionary<string, object?>(StringComparer.Ordinal);
        }

        if (RequestedUnsupportedEffects(conversation, capabilityMetadata).Count > 0)
        {
            return reasons;
        }

        var missing = MissingRequiredInputNames(conversation, capabilityMetadata)
            .Where(inputName => !parameters.ContainsKey(inputName))
            .ToArray();
        if (MissingRequiredInputsAreConcretelyReferenced(conversation, capabilityMetadata, missing))
        {
            reasons.Add($"missing required input(s) appear present but unbound: {string.Join(", ", missing.Order(StringComparer.Ordinal))}");
        }

        var requestedEffect = RequestedPrimaryContentEffect(conversation);
        var produced = CapabilityProduces(capabilityMetadata);
        if (requestedEffect is not null && !produced.Contains(requestedEffect) && !IsApprovalCapability(capabilityMetadata))
        {
            reasons.Add($"selected capability does not produce requested primary effect: {requestedEffect}");
        }

        return reasons;
    }

    private static List<string> OrderedTextTokens(object? value)
    {
        var normalized = StringValue(value).ToLowerInvariant().Replace('_', ' ');
        var tokens = new List<string>();
        foreach (Match match in TokenRegex().Matches(normalized))
        {
            var token = match.Value;
            if (token.Length > 1)
            {
                tokens.Add(token);
            }
        }

        return tokens;
    }

    private static IReadOnlySet<string> TokenVariants(IReadOnlySet<string> tokens)
    {
        var variants = new HashSet<string>(tokens, StringComparer.Ordinal);
        foreach (var token in tokens)
        {
            if (token.Length <= 3)
            {
                continue;
            }

            if (token.EndsWith("ies", StringComparison.Ordinal) && token.Length > 4)
            {
                variants.Add(token[..^3] + "y");
            }
            else if (token.EndsWith("ing", StringComparison.Ordinal) && token.Length > 5)
            {
                variants.Add(token[..^3]);
            }
            else if (token.EndsWith("ed", StringComparison.Ordinal) && token.Length > 4)
            {
                variants.Add(token[..^2]);
            }
            else if (token.EndsWith("es", StringComparison.Ordinal) && token.Length > 4)
            {
                variants.Add(token[..^2]);
            }
            else if (token.EndsWith('s') && token.Length > 4)
            {
                variants.Add(token[..^1]);
            }
            else
            {
                variants.Add(token + "s");
            }
        }

        return variants;
    }

    private static IReadOnlySet<string> ScoreTokens(object? value)
    {
        var filtered = TextTokens(value)
            .Where(token => !CapabilityScoringStopTokens.Contains(token) && !IsYearToken(token))
            .ToHashSet(StringComparer.Ordinal);
        return TokenVariants(filtered);
    }

    private static IReadOnlyDictionary<string, object?> MapValue(object? value)
    {
        if (value is JsonElement element)
        {
            if (element.ValueKind != JsonValueKind.Object)
            {
                return new Dictionary<string, object?>(StringComparer.Ordinal);
            }

            return element.EnumerateObject()
                .ToDictionary(property => property.Name, property => (object?)property.Value, StringComparer.Ordinal);
        }

        if (value is not IDictionary dictionary)
        {
            return new Dictionary<string, object?>(StringComparer.Ordinal);
        }

        var output = new Dictionary<string, object?>(StringComparer.Ordinal);
        foreach (DictionaryEntry entry in dictionary)
        {
            output[StringValue(entry.Key)] = entry.Value;
        }

        return output;
    }

    private static IReadOnlyList<object?> ListValue(object? value)
    {
        if (value is JsonElement element)
        {
            return element.ValueKind == JsonValueKind.Array
                ? element.EnumerateArray().Select(item => (object?)item).ToArray()
                : [];
        }

        if (value is string || value is not IEnumerable enumerable)
        {
            return [];
        }

        var output = new List<object?>();
        foreach (var item in enumerable)
        {
            output.Add(item);
        }

        return output;
    }

    private static IReadOnlyList<string> StringList(object? value)
    {
        return ListValue(value)
            .Select(StringValue)
            .Where(text => text.Length > 0)
            .ToArray();
    }

    private static string StringValue(object? value)
    {
        if (value is null)
        {
            return string.Empty;
        }

        if (value is JsonElement element)
        {
            return element.ValueKind switch
            {
                JsonValueKind.String => element.GetString()?.Trim() ?? string.Empty,
                JsonValueKind.Number or JsonValueKind.True or JsonValueKind.False => element.ToString().Trim(),
                JsonValueKind.Object or JsonValueKind.Array => element.GetRawText().Trim(),
                _ => string.Empty
            };
        }

        return Convert.ToString(value, System.Globalization.CultureInfo.InvariantCulture)?.Trim() ?? string.Empty;
    }

    private static bool BoolValue(object? value)
    {
        if (value is bool flag)
        {
            return flag;
        }

        if (value is JsonElement { ValueKind: JsonValueKind.True })
        {
            return true;
        }

        if (value is JsonElement { ValueKind: JsonValueKind.False })
        {
            return false;
        }

        return bool.TryParse(StringValue(value), out var parsed) && parsed;
    }

    private static object? GetValue(IReadOnlyDictionary<string, object?> map, string key)
    {
        return map.TryGetValue(key, out var value) ? value : null;
    }

    private static bool InputHasDefault(IReadOnlyDictionary<string, object?> spec)
    {
        if (!spec.TryGetValue("default", out var value) || value is null)
        {
            return false;
        }

        if (value is JsonElement element)
        {
            return element.ValueKind switch
            {
                JsonValueKind.Null or JsonValueKind.Undefined => false,
                JsonValueKind.String => !string.IsNullOrEmpty(element.GetString()),
                JsonValueKind.Array => element.GetArrayLength() > 0,
                _ => true
            };
        }

        return value is string text ? text.Length > 0 : value is not IEnumerable enumerable || enumerable.GetEnumerator().MoveNext();
    }

    private static IReadOnlyList<string> InputCandidateValues(
        IReadOnlyDictionary<string, object?> metadata,
        IReadOnlyDictionary<string, object?> spec)
    {
        var inputName = StringValue(GetValue(spec, "name"));
        var meanings = MapValue(GetValue(MapValue(GetValue(metadata, "app_profile")), "input_meanings"));
        var inputMeanings = MapValue(GetValue(meanings, inputName));
        var values = new List<string>(StringList(GetValue(spec, "allowed_values")));

        foreach (var (key, value) in inputMeanings)
        {
            if (key.Length > 0)
            {
                values.Add(key);
            }

            var text = StringValue(value);
            if (text.Length > 0)
            {
                values.Add(text);
            }
        }

        return values;
    }

    private static bool InputGrounded(string conversation, IReadOnlyList<string> values)
    {
        var conversationKey = SemanticTextKey(conversation);
        var conversationTokens = TextTokens(conversation);

        foreach (var value in values)
        {
            var valueKey = SemanticTextKey(value);
            if (valueKey.Length == 0)
            {
                continue;
            }

            if (conversationKey.Contains(valueKey, StringComparison.Ordinal))
            {
                return true;
            }

            var valueTokens = TextTokens(value);
            if (valueTokens.Count > 0 && valueTokens.All(conversationTokens.Contains))
            {
                return true;
            }
        }

        return false;
    }

    private static bool ConversationContainsValue(string conversation, string value)
    {
        var valueKey = SemanticTextKey(value);
        if (valueKey.Length == 0)
        {
            return false;
        }

        if (SemanticTextKey(conversation).Contains(valueKey, StringComparison.Ordinal))
        {
            return true;
        }

        var conversationTokens = TextTokens(conversation);
        var valueTokens = TextTokens(value);
        return valueTokens.Count > 0 && valueTokens.All(conversationTokens.Contains);
    }

    private static IReadOnlySet<string> CapabilityProduces(IReadOnlyDictionary<string, object?> metadata)
    {
        return StringList(GetValue(MapValue(GetValue(metadata, "business_effects")), "produces")).ToHashSet(StringComparer.Ordinal);
    }

    private static IReadOnlySet<string> CapabilityDoesNotProduce(IReadOnlyDictionary<string, object?> metadata)
    {
        var boundaries = AppBoundaries(metadata);
        var unsupported = StringList(GetValue(boundaries, "unsupported_effects"));
        return unsupported.Count > 0
            ? unsupported.ToHashSet(StringComparer.Ordinal)
            : StringList(GetValue(MapValue(GetValue(metadata, "business_effects")), "does_not_produce")).ToHashSet(StringComparer.Ordinal);
    }

    private static IReadOnlyDictionary<string, object?> AppBoundaries(IReadOnlyDictionary<string, object?> metadata)
    {
        var boundaries = MapValue(GetValue(MapValue(GetValue(metadata, "app_profile")), "app_boundaries"));
        return boundaries.Count > 0 ? boundaries : MapValue(GetValue(metadata, "app_boundaries"));
    }

    private static bool TermIsNegated(IReadOnlyList<string> tokens, string term)
    {
        for (var index = 0; index < tokens.Count; index++)
        {
            if (term != tokens[index])
            {
                continue;
            }

            var start = Math.Max(0, index - 6);
            var window = tokens.Skip(start).Take(index - start).ToArray();
            if (window.Any(NegationTerms.Contains))
            {
                return true;
            }

            if (window.Length >= 2 && window[^2] == "do" && window[^1] == "not")
            {
                return true;
            }
        }

        return false;
    }

    private static IReadOnlySet<string> InputReferenceTokens(IReadOnlyDictionary<string, object?> metadata, string inputName)
    {
        IReadOnlyDictionary<string, object?> spec = new Dictionary<string, object?>(StringComparer.Ordinal);
        foreach (var rawSpec in ListValue(GetValue(metadata, "input_specs")))
        {
            var candidate = MapValue(rawSpec);
            if (inputName == StringValue(GetValue(candidate, "name")))
            {
                spec = candidate;
                break;
            }
        }

        var tokens = TextTokens(
            string.Join(
                " ",
                [inputName, StringValue(GetValue(spec, "semantic_type")), StringValue(GetValue(spec, "description"))]))
            .ToHashSet(StringComparer.Ordinal);
        tokens.ExceptWith(WeakInputTokens);
        return tokens;
    }

    private static bool MissingRequiredInputsAreReferenced(
        string conversation,
        IReadOnlyDictionary<string, object?> metadata,
        IReadOnlyList<string> missingInputs)
    {
        if (missingInputs.Count == 0)
        {
            return false;
        }

        var conversationTokens = TextTokens(conversation);
        if (conversationTokens.Count == 0)
        {
            return false;
        }

        foreach (var inputName in missingInputs)
        {
            var tokens = InputReferenceTokens(metadata, inputName);
            if (tokens.Count == 0 || !tokens.Any(conversationTokens.Contains))
            {
                return false;
            }
        }

        return true;
    }

    private static bool MissingRequiredInputsAreConcretelyReferenced(
        string conversation,
        IReadOnlyDictionary<string, object?> metadata,
        IReadOnlyList<string> missingInputs)
    {
        if (missingInputs.Count == 0)
        {
            return false;
        }

        var specs = new Dictionary<string, IReadOnlyDictionary<string, object?>>(StringComparer.Ordinal);
        foreach (var rawSpec in ListValue(GetValue(metadata, "input_specs")))
        {
            var spec = MapValue(rawSpec);
            var name = StringValue(GetValue(spec, "name"));
            if (name.Length > 0)
            {
                specs[name] = spec;
            }
        }

        var conversationTokens = TextTokens(conversation);
        foreach (var inputName in missingInputs)
        {
            if (!specs.TryGetValue(inputName, out var spec))
            {
                return false;
            }

            var tokens = InputReferenceTokens(metadata, inputName);
            if (tokens.Count == 0
                || !tokens.Any(conversationTokens.Contains)
                || !MissingInputHasConcreteEvidence(conversation, spec, metadata))
            {
                return false;
            }
        }

        return true;
    }

    private static bool MissingInputHasConcreteEvidence(
        string conversation,
        IReadOnlyDictionary<string, object?> spec,
        IReadOnlyDictionary<string, object?> metadata)
    {
        var inputName = StringValue(GetValue(spec, "name")).ToLowerInvariant();
        var semanticType = StringValue(GetValue(spec, "semantic_type")).ToLowerInvariant();
        var rawType = StringValue(GetValue(spec, "type")).ToLowerInvariant();
        if (inputName.Contains("id", StringComparison.Ordinal) || semanticType.EndsWith("_id", StringComparison.Ordinal))
        {
            return IdentifierRegex().IsMatch(conversation);
        }

        if (semanticType == "time_scope"
            || inputName.Contains("quarter", StringComparison.Ordinal)
            || inputName.Contains("period", StringComparison.Ordinal)
            || inputName.Contains("date", StringComparison.Ordinal))
        {
            return QuarterRegex().IsMatch(conversation);
        }

        if (rawType is "integer" or "number" or "float"
            || inputName.Contains("limit", StringComparison.Ordinal)
            || inputName.Contains("count", StringComparison.Ordinal))
        {
            return NumberRegex().IsMatch(conversation);
        }

        var allowedValues = StringList(GetValue(spec, "allowed_values"));
        if (allowedValues.Count > 0)
        {
            return allowedValues.Any(value => ConversationContainsValue(conversation, value));
        }

        return InputReferenceTokens(metadata, StringValue(GetValue(spec, "name"))).Count > 0
            && ConcreteEntityRegex().IsMatch(conversation);
    }

    private static bool SameEffectClass(IReadOnlyDictionary<string, object?> first, IReadOnlyDictionary<string, object?> second)
    {
        var firstProduces = CapabilityProduces(first);
        var secondProduces = CapabilityProduces(second);
        return firstProduces.Any(secondProduces.Contains);
    }

    private static bool HasUnnegatedToken(IReadOnlySet<string> tokens, IReadOnlyList<string> orderedTokens, IReadOnlyList<string> terms)
    {
        return terms.Any(term => tokens.Contains(term) && !TermIsNegated(orderedTokens, term));
    }

    private static bool IsObjectValue(object? value)
    {
        return value is IDictionary || value is JsonElement { ValueKind: JsonValueKind.Object };
    }

    private static int Overlap(IReadOnlySet<string> first, IReadOnlySet<string> second)
    {
        return first.Count(second.Contains);
    }

    private static bool IsYearToken(string token)
    {
        return token.Length == 4
            && (token.StartsWith("19", StringComparison.Ordinal) || token.StartsWith("20", StringComparison.Ordinal))
            && token.All(char.IsDigit);
    }

    [GeneratedRegex("[a-z0-9]+")]
    private static partial Regex TokenRegex();

    [GeneratedRegex("[^a-z0-9]+")]
    private static partial Regex SemanticTextRegex();

    [GeneratedRegex(@"\b[A-Z][A-Z0-9]+-[A-Z0-9]+\b|\b[A-Za-z]+-\d+\b")]
    private static partial Regex IdentifierRegex();

    [GeneratedRegex(@"\b(?:19|20)\d{2}-Q[1-4]\b|\bQ[1-4]\s+(?:FY)?(?:19|20)?\d{2,4}\b", RegexOptions.IgnoreCase)]
    private static partial Regex QuarterRegex();

    [GeneratedRegex(@"\b\d+\b")]
    private static partial Regex NumberRegex();

    [GeneratedRegex(@"[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){1,3}|[_-]|\d")]
    private static partial Regex ConcreteEntityRegex();
}
