using System.Security.Cryptography;
using Anip.Core;

namespace Anip.Server;

/// <summary>
/// A single step in a Merkle inclusion proof.
/// </summary>
public class ProofStep
{
    public string Hash { get; set; } = "";
    public string Side { get; set; } = ""; // "left" or "right"
}

/// <summary>
/// RFC 6962 Merkle hash tree implementation.
/// </summary>
public class MerkleTree
{
    private readonly List<byte[]> _leaves = new();

    /// <summary>
    /// Adds a data element to the tree as a leaf.
    /// </summary>
    public void AddLeaf(byte[] data)
    {
        _leaves.Add(LeafHash(data));
    }

    /// <summary>
    /// Returns the number of leaves.
    /// </summary>
    public int LeafCount => _leaves.Count;

    /// <summary>
    /// Returns the Merkle root as "sha256:&lt;hex&gt;".
    /// </summary>
    public string Root()
    {
        if (_leaves.Count == 0)
        {
            var h = SHA256.HashData(Array.Empty<byte>());
            return $"sha256:{Convert.ToHexString(h).ToLowerInvariant()}";
        }

        var root = ComputeRoot(0, _leaves.Count);
        return $"sha256:{Convert.ToHexString(root).ToLowerInvariant()}";
    }

    /// <summary>
    /// Generates the inclusion proof path for the leaf at the given index.
    /// </summary>
    public List<ProofStep> InclusionProof(int index)
    {
        if (index < 0 || index >= _leaves.Count)
        {
            throw new ArgumentOutOfRangeException(nameof(index),
                $"leaf index {index} out of range [0, {_leaves.Count})");
        }

        var path = new List<ProofStep>();
        BuildInclusionPath(index, 0, _leaves.Count, path);
        return path;
    }

    /// <summary>
    /// Verifies that data at the given index is included in the tree with the expected root.
    /// </summary>
    public static bool VerifyInclusion(byte[] data, List<ProofStep> proof, string expectedRoot)
    {
        var current = LeafHash(data);

        foreach (var step in proof)
        {
            var sibling = HexToBytes(step.Hash);
            current = step.Side == "left"
                ? NodeHash(sibling, current)
                : NodeHash(current, sibling);
        }

        return $"sha256:{Convert.ToHexString(current).ToLowerInvariant()}" == expectedRoot;
    }

    /// <summary>
    /// Computes SHA256(0x00 || data) — the leaf hash per RFC 6962.
    /// </summary>
    internal static byte[] LeafHash(byte[] data)
    {
        var input = new byte[1 + data.Length];
        input[0] = Constants.LeafHashPrefix;
        Buffer.BlockCopy(data, 0, input, 1, data.Length);
        return SHA256.HashData(input);
    }

    /// <summary>
    /// Computes SHA256(0x01 || left || right) — the node hash per RFC 6962.
    /// </summary>
    internal static byte[] NodeHash(byte[] left, byte[] right)
    {
        var input = new byte[1 + left.Length + right.Length];
        input[0] = Constants.NodeHashPrefix;
        Buffer.BlockCopy(left, 0, input, 1, left.Length);
        Buffer.BlockCopy(right, 0, input, 1 + left.Length, right.Length);
        return SHA256.HashData(input);
    }

    private byte[] ComputeRoot(int lo, int hi)
    {
        var n = hi - lo;
        if (n == 1)
            return _leaves[lo];

        var split = LargestPowerOf2LessThan(n);
        var left = ComputeRoot(lo, lo + split);
        var right = ComputeRoot(lo + split, hi);
        return NodeHash(left, right);
    }

    private void BuildInclusionPath(int index, int lo, int hi, List<ProofStep> path)
    {
        var n = hi - lo;
        if (n == 1)
            return;

        var split = LargestPowerOf2LessThan(n);
        if (index - lo < split)
        {
            BuildInclusionPath(index, lo, lo + split, path);
            var right = ComputeRoot(lo + split, hi);
            path.Add(new ProofStep
            {
                Hash = Convert.ToHexString(right).ToLowerInvariant(),
                Side = "right"
            });
        }
        else
        {
            BuildInclusionPath(index, lo + split, hi, path);
            var left = ComputeRoot(lo, lo + split);
            path.Add(new ProofStep
            {
                Hash = Convert.ToHexString(left).ToLowerInvariant(),
                Side = "left"
            });
        }
    }

    private static int LargestPowerOf2LessThan(int n)
    {
        if (n <= 1)
            return 0;
        var k = 1;
        while (k * 2 < n)
            k *= 2;
        return k;
    }

    private static byte[] HexToBytes(string hex)
    {
        var bytes = new byte[hex.Length / 2];
        for (int i = 0; i < bytes.Length; i++)
        {
            bytes[i] = Convert.ToByte(hex.Substring(i * 2, 2), 16);
        }
        return bytes;
    }
}
