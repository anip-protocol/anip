using Anip.Core;

namespace Anip.Rest;

/// <summary>
/// A single REST endpoint generated from an ANIP capability.
/// </summary>
public class RestRoute
{
    public string CapabilityName { get; }
    public string Path { get; }
    public string Method { get; } // "GET" or "POST"
    public CapabilityDeclaration Declaration { get; }

    public RestRoute(string capabilityName, string path, string method,
                     CapabilityDeclaration declaration)
    {
        CapabilityName = capabilityName;
        Path = path;
        Method = method;
        Declaration = declaration;
    }
}
