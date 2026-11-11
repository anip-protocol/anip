namespace Anip.Service;

/// <summary>
/// Identifies who is asking for a token and how they proved it.
/// </summary>
/// <param name="Principal">The authenticated caller.</param>
/// <param name="ViaToken">
/// True when the caller authenticated with a delegation token issued by this
/// service rather than with a bootstrap credential.
/// </param>
public sealed record Issuer(string Principal, bool ViaToken);
