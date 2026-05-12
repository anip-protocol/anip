using System.Text.Json;
using System.Text.Json.Serialization;

namespace Anip.Core;

[JsonConverter(typeof(ResolutionBehaviorJsonConverter))]
public enum ResolutionBehavior
{
    Clarify,
    UseDefault,
    UseActorScope,
    AppSelectOrClarify,
    Deny,
    DenyOrClarify,
    Omit
}

public class ResolutionBehaviorJsonConverter : JsonConverter<ResolutionBehavior>
{
    public override ResolutionBehavior Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) =>
        reader.GetString() switch
        {
            "clarify" => ResolutionBehavior.Clarify,
            "use_default" => ResolutionBehavior.UseDefault,
            "use_actor_scope" => ResolutionBehavior.UseActorScope,
            "app_select_or_clarify" => ResolutionBehavior.AppSelectOrClarify,
            "deny" => ResolutionBehavior.Deny,
            "deny_or_clarify" => ResolutionBehavior.DenyOrClarify,
            "omit" => ResolutionBehavior.Omit,
            var s => throw new JsonException($"invalid resolution behavior: {s}")
        };

    public override void Write(Utf8JsonWriter writer, ResolutionBehavior value, JsonSerializerOptions options) =>
        writer.WriteStringValue(value switch
        {
            ResolutionBehavior.Clarify => "clarify",
            ResolutionBehavior.UseDefault => "use_default",
            ResolutionBehavior.UseActorScope => "use_actor_scope",
            ResolutionBehavior.AppSelectOrClarify => "app_select_or_clarify",
            ResolutionBehavior.Deny => "deny",
            ResolutionBehavior.DenyOrClarify => "deny_or_clarify",
            ResolutionBehavior.Omit => "omit",
            _ => throw new InvalidOperationException()
        });
}
