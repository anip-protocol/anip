using System.Security.Cryptography;
using System.Text;
using Anip.Core;
using Anip.Server;
using Xunit;

namespace Anip.Server.Tests;

public class MerkleTreeTests
{
    [Fact]
    public void EmptyTree_Root()
    {
        var tree = new MerkleTree();
        var root = tree.Root();

        // Empty tree root is SHA-256 of empty input.
        var expected = SHA256.HashData(Array.Empty<byte>());
        Assert.Equal($"sha256:{Convert.ToHexString(expected).ToLowerInvariant()}", root);
    }

    [Fact]
    public void SingleLeaf()
    {
        var tree = new MerkleTree();
        var data = Encoding.UTF8.GetBytes("hello");
        tree.AddLeaf(data);

        var root = tree.Root();
        Assert.StartsWith("sha256:", root);

        // For a single leaf, root == leaf hash.
        var leafHash = SHA256.HashData(new byte[] { Constants.LeafHashPrefix }.Concat(data).ToArray());
        Assert.Equal($"sha256:{Convert.ToHexString(leafHash).ToLowerInvariant()}", root);
    }

    [Fact]
    public void TwoLeaves()
    {
        var tree = new MerkleTree();
        var data1 = Encoding.UTF8.GetBytes("leaf1");
        var data2 = Encoding.UTF8.GetBytes("leaf2");
        tree.AddLeaf(data1);
        tree.AddLeaf(data2);

        var root = tree.Root();
        Assert.StartsWith("sha256:", root);

        // Compute expected root manually.
        var h1 = SHA256.HashData(new byte[] { Constants.LeafHashPrefix }.Concat(data1).ToArray());
        var h2 = SHA256.HashData(new byte[] { Constants.LeafHashPrefix }.Concat(data2).ToArray());
        var nodeInput = new byte[] { Constants.NodeHashPrefix }.Concat(h1).Concat(h2).ToArray();
        var expectedRoot = SHA256.HashData(nodeInput);

        Assert.Equal($"sha256:{Convert.ToHexString(expectedRoot).ToLowerInvariant()}", root);
    }

    [Fact]
    public void PowerOfTwo_FourLeaves()
    {
        var tree = new MerkleTree();
        for (int i = 0; i < 4; i++)
        {
            tree.AddLeaf(Encoding.UTF8.GetBytes($"leaf-{i}"));
        }

        var root = tree.Root();
        Assert.StartsWith("sha256:", root);
        Assert.Equal(4, tree.LeafCount);
    }

    [Fact]
    public void NonPowerOfTwo_ThreeLeaves()
    {
        var tree = new MerkleTree();
        for (int i = 0; i < 3; i++)
        {
            tree.AddLeaf(Encoding.UTF8.GetBytes($"leaf-{i}"));
        }

        var root = tree.Root();
        Assert.StartsWith("sha256:", root);
        Assert.Equal(3, tree.LeafCount);
    }

    [Fact]
    public void NonPowerOfTwo_FiveLeaves()
    {
        var tree = new MerkleTree();
        for (int i = 0; i < 5; i++)
        {
            tree.AddLeaf(Encoding.UTF8.GetBytes($"leaf-{i}"));
        }

        var root = tree.Root();
        Assert.StartsWith("sha256:", root);
        Assert.Equal(5, tree.LeafCount);
    }

    [Fact]
    public void InclusionProof_SingleLeaf()
    {
        var tree = new MerkleTree();
        var data = Encoding.UTF8.GetBytes("only-leaf");
        tree.AddLeaf(data);

        var proof = tree.InclusionProof(0);
        Assert.Empty(proof); // Single leaf, no siblings needed.

        // Verify inclusion.
        var root = tree.Root();
        var valid = MerkleTree.VerifyInclusion(data, proof, root);
        Assert.True(valid);
    }

    [Fact]
    public void InclusionProof_TwoLeaves()
    {
        var tree = new MerkleTree();
        var data0 = Encoding.UTF8.GetBytes("leaf-0");
        var data1 = Encoding.UTF8.GetBytes("leaf-1");
        tree.AddLeaf(data0);
        tree.AddLeaf(data1);

        var root = tree.Root();

        // Proof for leaf 0.
        var proof0 = tree.InclusionProof(0);
        Assert.Single(proof0);
        Assert.Equal("right", proof0[0].Side);
        Assert.True(MerkleTree.VerifyInclusion(data0, proof0, root));

        // Proof for leaf 1.
        var proof1 = tree.InclusionProof(1);
        Assert.Single(proof1);
        Assert.Equal("left", proof1[0].Side);
        Assert.True(MerkleTree.VerifyInclusion(data1, proof1, root));
    }

    [Fact]
    public void InclusionProof_FourLeaves()
    {
        var tree = new MerkleTree();
        var leafData = new List<byte[]>();
        for (int i = 0; i < 4; i++)
        {
            var data = Encoding.UTF8.GetBytes($"leaf-{i}");
            leafData.Add(data);
            tree.AddLeaf(data);
        }

        var root = tree.Root();

        // Verify all leaf inclusions.
        for (int i = 0; i < 4; i++)
        {
            var proof = tree.InclusionProof(i);
            Assert.Equal(2, proof.Count); // log2(4) = 2 steps.
            Assert.True(MerkleTree.VerifyInclusion(leafData[i], proof, root));
        }
    }

    [Fact]
    public void InclusionProof_ThreeLeaves()
    {
        var tree = new MerkleTree();
        var leafData = new List<byte[]>();
        for (int i = 0; i < 3; i++)
        {
            var data = Encoding.UTF8.GetBytes($"leaf-{i}");
            leafData.Add(data);
            tree.AddLeaf(data);
        }

        var root = tree.Root();

        for (int i = 0; i < 3; i++)
        {
            var proof = tree.InclusionProof(i);
            Assert.True(MerkleTree.VerifyInclusion(leafData[i], proof, root));
        }
    }

    [Fact]
    public void InclusionProof_SevenLeaves()
    {
        var tree = new MerkleTree();
        var leafData = new List<byte[]>();
        for (int i = 0; i < 7; i++)
        {
            var data = Encoding.UTF8.GetBytes($"leaf-{i}");
            leafData.Add(data);
            tree.AddLeaf(data);
        }

        var root = tree.Root();

        for (int i = 0; i < 7; i++)
        {
            var proof = tree.InclusionProof(i);
            Assert.True(MerkleTree.VerifyInclusion(leafData[i], proof, root),
                $"Inclusion proof failed for leaf {i}");
        }
    }

    [Fact]
    public void InclusionProof_InvalidData_Fails()
    {
        var tree = new MerkleTree();
        tree.AddLeaf(Encoding.UTF8.GetBytes("leaf-0"));
        tree.AddLeaf(Encoding.UTF8.GetBytes("leaf-1"));

        var root = tree.Root();
        var proof = tree.InclusionProof(0);

        // Using wrong data should fail verification.
        var wrongData = Encoding.UTF8.GetBytes("wrong-data");
        Assert.False(MerkleTree.VerifyInclusion(wrongData, proof, root));
    }

    [Fact]
    public void InclusionProof_OutOfRange_Throws()
    {
        var tree = new MerkleTree();
        tree.AddLeaf(Encoding.UTF8.GetBytes("leaf-0"));

        Assert.Throws<ArgumentOutOfRangeException>(() => tree.InclusionProof(-1));
        Assert.Throws<ArgumentOutOfRangeException>(() => tree.InclusionProof(1));
    }

    [Fact]
    public void DeterministicRoot()
    {
        // Same data should produce same root.
        var tree1 = new MerkleTree();
        var tree2 = new MerkleTree();

        for (int i = 0; i < 5; i++)
        {
            var data = Encoding.UTF8.GetBytes($"leaf-{i}");
            tree1.AddLeaf(data);
            tree2.AddLeaf(data);
        }

        Assert.Equal(tree1.Root(), tree2.Root());
    }
}
