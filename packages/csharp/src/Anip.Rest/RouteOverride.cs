namespace Anip.Rest;

/// <summary>
/// Allows customizing the path and/or method for a capability route.
/// </summary>
public class RouteOverride
{
    public string? Path { get; }
    public string? Method { get; }

    public RouteOverride(string? path, string? method)
    {
        Path = path;
        Method = method;
    }
}
