using System.Text.Json;

using Anip.Core;

namespace Anip.Mcp;

/// <summary>
/// Translates ANIP capabilities to MCP tools with JSON Schema inputs
/// and enriched descriptions.
/// </summary>
public static class McpToolTranslator
{
    private static readonly Dictionary<string, string> TypeMap = new()
    {
        ["string"] = "string",
        ["integer"] = "integer",
        ["number"] = "number",
        ["boolean"] = "boolean",
        ["date"] = "string",
        ["airport_code"] = "string",
    };

    /// <summary>
    /// Builds an MCP tool spec from an ANIP capability declaration.
    /// Returns a dictionary with name, description, inputSchema, and annotations.
    /// </summary>
    public static Dictionary<string, object?> BuildTool(
        string name, CapabilityDeclaration decl, bool enrichDescriptions)
    {
        var description = enrichDescriptions
            ? EnrichDescription(decl)
            : decl.Description;

        var inputSchema = BuildInputSchema(decl);

        var readOnly = decl.SideEffect is { Type: "read" };
        var destructive = decl.SideEffect is { Type: "irreversible" };

        var annotations = new Dictionary<string, object?>
        {
            ["readOnlyHint"] = readOnly,
            ["destructiveHint"] = destructive,
        };

        return new Dictionary<string, object?>
        {
            ["name"] = name,
            ["description"] = description,
            ["inputSchema"] = inputSchema,
            ["annotations"] = annotations,
        };
    }

    /// <summary>
    /// Converts capability inputs to an MCP-compatible JSON Schema dictionary.
    /// </summary>
    public static Dictionary<string, object?> BuildInputSchema(CapabilityDeclaration decl)
    {
        var properties = new Dictionary<string, object?>();
        var required = new List<string>();

        if (decl.Inputs != null)
        {
            foreach (var input in decl.Inputs)
            {
                var jsonType = TypeMap.GetValueOrDefault(input.Type, "string");

                var prop = new Dictionary<string, object?>
                {
                    ["type"] = jsonType,
                };

                if (input.Description != null)
                {
                    prop["description"] = input.Description;
                }

                if (input.Type == "date")
                {
                    prop["format"] = "date";
                }

                if (input.Default != null)
                {
                    prop["default"] = input.Default;
                }

                properties[input.Name] = prop;

                if (input.Required)
                {
                    required.Add(input.Name);
                }
            }
        }

        var schema = new Dictionary<string, object?>
        {
            ["type"] = "object",
            ["properties"] = properties,
        };

        if (required.Count > 0)
        {
            schema["required"] = required;
        }

        return schema;
    }

    /// <summary>
    /// Builds an enriched description with ANIP metadata including
    /// side effects, cost, prerequisites, and scope info.
    /// </summary>
    public static string EnrichDescription(CapabilityDeclaration decl)
    {
        var parts = new List<string> { decl.Description };

        if (decl.SideEffect != null && !string.IsNullOrEmpty(decl.SideEffect.Type))
        {
            switch (decl.SideEffect.Type)
            {
                case "irreversible":
                    parts.Add("WARNING: IRREVERSIBLE action — cannot be undone.");
                    if (decl.SideEffect.RollbackWindow == "none")
                    {
                        parts.Add("No rollback window.");
                    }
                    break;

                case "write":
                    var rbw = decl.SideEffect.RollbackWindow;
                    if (!string.IsNullOrEmpty(rbw) && rbw != "none" && rbw != "not_applicable")
                    {
                        parts.Add($"Reversible within {rbw}.");
                    }
                    break;

                case "read":
                    parts.Add("Read-only, no side effects.");
                    break;
            }
        }

        if (decl.Cost != null)
        {
            var certainty = decl.Cost.Certainty;
            var financial = decl.Cost.Financial;

            if (certainty == "fixed" && financial != null)
            {
                var currency = !string.IsNullOrEmpty(financial.Currency) ? financial.Currency : "USD";
                if (financial.Amount != null)
                {
                    parts.Add($"Cost: {currency} {financial.Amount} (fixed).");
                }
            }
            else if (certainty == "estimated" && financial != null)
            {
                var currency = !string.IsNullOrEmpty(financial.Currency) ? financial.Currency : "USD";

                if (financial.RangeMin != null && financial.RangeMax != null)
                {
                    parts.Add($"Estimated cost: {currency} {financial.RangeMin}-{financial.RangeMax}.");
                }
            }
        }

        if (decl.Requires is { Count: > 0 })
        {
            var prereqs = decl.Requires.Select(r => r.Capability).ToList();
            parts.Add($"Requires calling first: {string.Join(", ", prereqs)}.");
        }

        if (decl.MinimumScope is { Count: > 0 })
        {
            parts.Add($"Delegation scope: {string.Join(", ", decl.MinimumScope)}.");
        }

        return string.Join(" ", parts);
    }

    /// <summary>
    /// Translates an ANIP invoke result dictionary to an MCP text result.
    /// </summary>
    public static McpInvokeResult TranslateResponse(Dictionary<string, object?> response)
    {
        var success = response.TryGetValue("success", out var successVal)
                      && successVal is true;

        if (success)
        {
            response.TryGetValue("result", out var result);
            string text;
            try
            {
                text = JsonSerializer.Serialize(result, new JsonSerializerOptions
                {
                    WriteIndented = true,
                });
            }
            catch
            {
                text = result?.ToString() ?? "";
            }

            // Append cost annotation if present.
            if (response.TryGetValue("cost_actual", out var costActualRaw)
                && costActualRaw is Dictionary<string, object?> costMap
                && costMap.TryGetValue("financial", out var financialRaw)
                && financialRaw is Dictionary<string, object?> financial)
            {
                financial.TryGetValue("amount", out var amount);
                var currency = financial.TryGetValue("currency", out var curr)
                    ? curr?.ToString() ?? "USD"
                    : "USD";
                if (amount != null)
                {
                    text += $"\n[Cost: {currency} {amount}]";
                }
            }

            return new McpInvokeResult(text, false);
        }

        // Failure path.
        if (!response.TryGetValue("failure", out var failureRaw)
            || failureRaw is not Dictionary<string, object?> failure)
        {
            return new McpInvokeResult("FAILED: unknown\nDetail: no detail\nRetryable: no", true);
        }

        var failType = failure.TryGetValue("type", out var ft)
            ? ft?.ToString() ?? "unknown"
            : "unknown";
        var detail = failure.TryGetValue("detail", out var dt)
            ? dt?.ToString() ?? "no detail"
            : "no detail";

        var textParts = new List<string>
        {
            $"FAILED: {failType}",
            $"Detail: {detail}",
        };

        if (failure.TryGetValue("resolution", out var resRaw)
            && resRaw is Dictionary<string, object?> res)
        {
            if (res.TryGetValue("action", out var action)
                && action is string actionStr && !string.IsNullOrEmpty(actionStr))
            {
                textParts.Add($"Resolution: {actionStr}");
            }
            if (res.TryGetValue("requires", out var requires)
                && requires is string requiresStr && !string.IsNullOrEmpty(requiresStr))
            {
                textParts.Add($"Requires: {requiresStr}");
            }
        }

        var retry = failure.TryGetValue("retry", out var retryVal) && retryVal is true;
        textParts.Add(retry ? "Retryable: yes" : "Retryable: no");

        return new McpInvokeResult(string.Join("\n", textParts), true);
    }
}
