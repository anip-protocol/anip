using Anip.Core;

namespace Anip.Service;

/// <summary>
/// Binds a capability declaration to a handler function.
/// </summary>
public class CapabilityDef
{
    public CapabilityDeclaration Declaration { get; }
    public Func<InvocationContext, Dictionary<string, object?>, Dictionary<string, object?>> Handler { get; }

    public CapabilityDef(
        CapabilityDeclaration declaration,
        Func<InvocationContext, Dictionary<string, object?>, Dictionary<string, object?>> handler)
    {
        Declaration = declaration;
        Handler = handler;
    }
}
