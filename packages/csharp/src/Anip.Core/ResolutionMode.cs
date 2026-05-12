using System.Text.Json;
using System.Text.Json.Serialization;

namespace Anip.Core;

[JsonConverter(typeof(ResolutionModeJsonConverter))]
public enum ResolutionMode
{
    ClosedValues,
    BackendResolved,
    AppSelected,
    ActorPolicy,
    ActorPolicyOrExplicit,
    ExplicitOnly,
    Clarify
}

public class ResolutionModeJsonConverter : JsonConverter<ResolutionMode>
{
    public override ResolutionMode Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) =>
        reader.GetString() switch
        {
            "closed_values" => ResolutionMode.ClosedValues,
            "backend_resolved" => ResolutionMode.BackendResolved,
            "app_selected" => ResolutionMode.AppSelected,
            "actor_policy" => ResolutionMode.ActorPolicy,
            "actor_policy_or_explicit" => ResolutionMode.ActorPolicyOrExplicit,
            "explicit_only" => ResolutionMode.ExplicitOnly,
            "clarify" => ResolutionMode.Clarify,
            var s => throw new JsonException($"invalid resolution.mode: {s}")
        };

    public override void Write(Utf8JsonWriter writer, ResolutionMode value, JsonSerializerOptions options) =>
        writer.WriteStringValue(value switch
        {
            ResolutionMode.ClosedValues => "closed_values",
            ResolutionMode.BackendResolved => "backend_resolved",
            ResolutionMode.AppSelected => "app_selected",
            ResolutionMode.ActorPolicy => "actor_policy",
            ResolutionMode.ActorPolicyOrExplicit => "actor_policy_or_explicit",
            ResolutionMode.ExplicitOnly => "explicit_only",
            ResolutionMode.Clarify => "clarify",
            _ => throw new InvalidOperationException()
        });
}
