namespace Anip.Service;

/// <summary>
/// Holds a manifest's canonical JSON bytes and its detached JWS signature.
/// </summary>
public class SignedManifest
{
    /// <summary>The canonical JSON bytes of the manifest.</summary>
    public byte[] ManifestJson { get; }

    /// <summary>The detached JWS signature (header..signature).</summary>
    public string Signature { get; }

    public SignedManifest(byte[] manifestJson, string signature)
    {
        ManifestJson = manifestJson;
        Signature = signature;
    }
}
