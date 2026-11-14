using System.Collections;
using System.Numerics;
using System.Text.Json;
using System.Text.Json.Nodes;
using Anip.Core;

namespace Anip.Service;

/// <summary>
/// SPEC.md §6.3 "Parameter Validation": checks an invocation's parameters, as
/// the caller sent them, against the capability's declared inputs. Declared
/// defaults, <c>allowed_values</c> and the <c>resolution</c> block play no part.
/// </summary>
public static class ParameterValidation
{
    /// <summary>The <c>resolution.requires</c> text of every refusal made by this check.</summary>
    public const string Requires = "parameters that match the capability's declared inputs";

    private static readonly HashSet<string> s_primitives = new(StringComparer.Ordinal)
    {
        "string", "integer", "number", "boolean", "array", "object",
    };

    /// <summary>
    /// Returns the failure detail when <paramref name="parameters"/> do not
    /// match the declared inputs, or null when they do. Absent parameters
    /// count as an empty object. Every missing required input is named, in
    /// declaration order; when none is missing, every undeclared parameter is,
    /// in RFC 8785 member order (UTF-16 code units, §4.7); when none is
    /// undeclared, every input whose value has the wrong primitive type is.
    /// </summary>
    public static string? Check(
        string capability,
        CapabilityDeclaration declaration,
        IReadOnlyDictionary<string, object?>? parameters)
    {
        var inputs = declaration.Inputs ?? new List<CapabilityInput>();

        var missing = new List<string>();
        foreach (var input in inputs)
        {
            if (input.MustBeSupplied() && JsonTypeOf(Supplied(parameters, input.Name)) == null)
            {
                missing.Add(input.Name);
            }
        }
        if (missing.Count > 0)
        {
            return $"{capability} is missing required input(s): {string.Join(", ", missing)}";
        }

        // Every key must name a declared input, whatever its value.
        var declaredNames = new HashSet<string>(inputs.Select(input => input.Name), StringComparer.Ordinal);
        var undeclared = (parameters?.Keys ?? Enumerable.Empty<string>())
            .Where(key => !declaredNames.Contains(key))
            .OrderBy(key => key, StringComparer.Ordinal)
            .ToList();
        if (undeclared.Count > 0)
        {
            return $"{capability} has undeclared parameter(s): {string.Join(", ", undeclared)}";
        }

        var wrong = new List<string>();
        foreach (var input in inputs)
        {
            var value = Supplied(parameters, input.Name);
            var received = JsonTypeOf(value);
            if (received == null) continue;
            // Exact, case-sensitive: any other type name is the handler's to validate.
            if (!s_primitives.Contains(input.Type)) continue;
            var ok = input.Type switch
            {
                "integer" => received == "number" && IsIntegral(value!),
                _ => received == input.Type,
            };
            if (!ok)
            {
                wrong.Add($"'{input.Name}' must be {input.Type}, got {received}");
            }
        }
        if (wrong.Count > 0)
        {
            return $"{capability} has invalid input(s): {string.Join("; ", wrong)}";
        }
        return null;
    }

    /// <summary>
    /// The <c>invalid_parameters</c> failure object for a refusal with the given detail.
    /// </summary>
    public static Dictionary<string, object?> Failure(string detail) => new()
    {
        ["type"] = Constants.FailureInvalidParameters,
        ["detail"] = detail,
        ["resolution"] = new Dictionary<string, object?>
        {
            ["action"] = "retry_now",
            ["recovery_class"] = Constants.RecoveryClassForAction("retry_now"),
            ["requires"] = Requires,
        },
        ["retry"] = false,
    };

    /// <summary>
    /// The JSON type of a parameter value — <c>string</c>, <c>number</c>,
    /// <c>boolean</c>, <c>array</c> or <c>object</c> — or null for JSON
    /// <c>null</c>. Transports hand the service <see cref="JsonElement"/>
    /// values, CLR values, or a mix of both.
    /// </summary>
    public static string? JsonTypeOf(object? value)
    {
        switch (value)
        {
            case null:
                return null;
            case JsonElement element:
                return element.ValueKind switch
                {
                    JsonValueKind.Null or JsonValueKind.Undefined => null,
                    JsonValueKind.String => "string",
                    JsonValueKind.Number => "number",
                    JsonValueKind.True or JsonValueKind.False => "boolean",
                    JsonValueKind.Array => "array",
                    _ => "object",
                };
            case JsonNode node:
                return node.GetValueKind() switch
                {
                    JsonValueKind.Null or JsonValueKind.Undefined => null,
                    JsonValueKind.String => "string",
                    JsonValueKind.Number => "number",
                    JsonValueKind.True or JsonValueKind.False => "boolean",
                    JsonValueKind.Array => "array",
                    _ => "object",
                };
            // A boolean is never a number.
            case bool:
                return "boolean";
            case string or char:
                return "string";
            case sbyte or byte or short or ushort or int or uint or long or ulong
                or float or double or decimal or BigInteger or Half or Int128 or UInt128:
                return "number";
            case IDictionary:
                return "object";
            case IEnumerable enumerable:
                return IsMap(enumerable) ? "object" : "array";
            default:
                return "object";
        }
    }

    private static object? Supplied(IReadOnlyDictionary<string, object?>? parameters, string name) =>
        parameters != null && parameters.TryGetValue(name, out var value) ? value : null;

    /// <summary>Generic dictionaries that do not implement the non-generic <see cref="IDictionary"/>.</summary>
    private static bool IsMap(IEnumerable value)
    {
        foreach (var contract in value.GetType().GetInterfaces())
        {
            if (!contract.IsGenericType) continue;
            var definition = contract.GetGenericTypeDefinition();
            if (definition == typeof(IDictionary<,>) || definition == typeof(IReadOnlyDictionary<,>))
            {
                return true;
            }
        }
        return false;
    }

    /// <summary>
    /// Whether a number is finite and has no fractional part. <c>5</c>,
    /// <c>5.0</c> and <c>1e2</c> are integral, as is an integer of any size.
    /// </summary>
    private static bool IsIntegral(object value)
    {
        switch (value)
        {
            case JsonElement element:
                if (element.TryGetInt64(out _)) return true;
                var text = element.GetRawText();
                // An integer literal too large for 64 bits.
                if (text.IndexOfAny(new[] { '.', 'e', 'E' }) < 0) return true;
                return element.TryGetDouble(out var parsed) && IsIntegral(parsed);
            case JsonNode node:
                return IsIntegral(JsonSerializer.SerializeToElement(node));
            case double d:
                return IsIntegral(d);
            case float f:
                return IsIntegral((double)f);
            case Half h:
                return IsIntegral((double)h);
            case decimal m:
                return decimal.Truncate(m) == m;
            default:
                // The integer types and BigInteger.
                return true;
        }
    }

    private static bool IsIntegral(double value) => double.IsFinite(value) && Math.Floor(value) == value;
}

/// <summary>
/// An invocation the service refused before the handler on a path that reports
/// refusals by exception (<see cref="AnipService.InvokeStream"/>).
/// <see cref="Response"/> is the response a unary invocation returns for the
/// same refusal: the failure, the <c>invocation_id</c> and the echoed lineage
/// fields.
/// </summary>
public sealed class InvocationRefusedError : AnipError
{
    public Dictionary<string, object?> Response { get; }

    public InvocationRefusedError(
        string errorType,
        string detail,
        Resolution? resolution,
        bool retry,
        Dictionary<string, object?> response)
        : base(errorType, detail, resolution, retry)
    {
        Response = response;
    }
}
