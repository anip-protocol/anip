namespace Anip.GraphQL;

/// <summary>
/// Maps ANIP snake_case invoke results to GraphQL camelCase response shape.
/// </summary>
public static class GraphQLResponseMapper
{
    /// <summary>
    /// Converts snake_case to camelCase.
    /// e.g. "cost_actual" -> "costActual"
    /// </summary>
    public static string ToCamelCase(string snake)
    {
        if (string.IsNullOrEmpty(snake)) return snake;
        var parts = snake.Split('_');
        var sb = new System.Text.StringBuilder(parts[0]);
        for (int i = 1; i < parts.Length; i++)
        {
            if (parts[i].Length > 0)
            {
                sb.Append(char.ToUpper(parts[i][0]));
                sb.Append(parts[i][1..]);
            }
        }
        return sb.ToString();
    }

    /// <summary>
    /// Converts camelCase to snake_case.
    /// e.g. "searchFlights" -> "search_flights"
    /// </summary>
    public static string ToSnakeCase(string camel)
    {
        if (string.IsNullOrEmpty(camel)) return camel;
        var sb = new System.Text.StringBuilder();
        for (int i = 0; i < camel.Length; i++)
        {
            var c = camel[i];
            if (char.IsUpper(c))
            {
                if (i > 0) sb.Append('_');
                sb.Append(char.ToLower(c));
            }
            else
            {
                sb.Append(c);
            }
        }
        return sb.ToString();
    }

    /// <summary>
    /// Converts snake_case to PascalCase.
    /// </summary>
    public static string ToPascalCase(string snake)
    {
        if (string.IsNullOrEmpty(snake)) return snake;
        var parts = snake.Split('_');
        var sb = new System.Text.StringBuilder();
        foreach (var part in parts)
        {
            if (part.Length > 0)
            {
                sb.Append(char.ToUpper(part[0]));
                sb.Append(part[1..]);
            }
        }
        return sb.ToString();
    }

    /// <summary>
    /// Maps an ANIP invoke result (snake_case) to GraphQL result shape (camelCase).
    /// </summary>
    public static Dictionary<string, object?> BuildGraphQLResponse(Dictionary<string, object?> result)
    {
        var response = new Dictionary<string, object?>
        {
            ["success"] = result.GetValueOrDefault("success", false),
            ["result"] = result.GetValueOrDefault("result"),
            ["costActual"] = null,
            ["failure"] = null,
        };

        if (result.TryGetValue("cost_actual", out var costActualRaw) && costActualRaw is Dictionary<string, object?> costMap)
        {
            response["costActual"] = new Dictionary<string, object?>
            {
                ["financial"] = costMap.GetValueOrDefault("financial"),
                ["varianceFromEstimate"] = costMap.GetValueOrDefault("variance_from_estimate"),
            };
        }

        if (result.TryGetValue("failure", out var failureRaw) && failureRaw is Dictionary<string, object?> failure)
        {
            var f = new Dictionary<string, object?>
            {
                ["type"] = failure.GetValueOrDefault("type", "unknown"),
                ["detail"] = failure.GetValueOrDefault("detail", ""),
                ["resolution"] = null,
                ["retry"] = failure.GetValueOrDefault("retry", false),
            };

            if (failure.TryGetValue("resolution", out var resolutionRaw) && resolutionRaw is Dictionary<string, object?> res)
            {
                f["resolution"] = new Dictionary<string, object?>
                {
                    ["action"] = res.GetValueOrDefault("action"),
                    ["requires"] = res.GetValueOrDefault("requires"),
                    ["grantableBy"] = res.GetValueOrDefault("grantable_by"),
                };
            }

            response["failure"] = f;
        }

        return response;
    }
}
