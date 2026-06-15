namespace GTMPipelineQ2Review;

public readonly record struct PolicyDecision(string Decision, string? Detail);

public static class Policy
{
    public static PolicyDecision Evaluate(
        Dictionary<string, object?> capability,
        Dictionary<string, object?> parameters,
        string? rootPrincipal)
    {
        return new PolicyDecision(
            "allow",
            "GTM C# native bundle evaluates actor and approval behavior in its backend adapter.");
    }
}
