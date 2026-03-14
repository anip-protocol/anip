"""RFC 6962 Merkle tree with inclusion and consistency proofs."""
import hashlib
from typing import Any


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _leaf_hash(data: bytes) -> bytes:
    """RFC 6962 §2.1: MTH({d(0)}) = SHA-256(0x00 || d(0))"""
    return _sha256(b"\x00" + data)


def _node_hash(left: bytes, right: bytes) -> bytes:
    """RFC 6962 §2.1: SHA-256(0x01 || left || right)"""
    return _sha256(b"\x01" + left + right)


def _hex(digest: bytes) -> str:
    return f"sha256:{digest.hex()}"


def _unhex(s: str) -> bytes:
    """Inverse of _hex: 'sha256:<hex>' -> bytes."""
    if s.startswith("sha256:"):
        return bytes.fromhex(s[7:])
    return bytes.fromhex(s)


def _is_power_of_2(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _largest_power_of_2_less_than(n: int) -> int:
    if n <= 1:
        return 0
    k = 1
    while k * 2 < n:
        k *= 2
    return k


class MerkleTree:
    """Append-only Merkle tree following RFC 6962 structure."""

    def __init__(self) -> None:
        self._leaves: list[bytes] = []

    @property
    def leaf_count(self) -> int:
        return len(self._leaves)

    @property
    def root(self) -> str:
        if not self._leaves:
            return _hex(_sha256(b""))
        return _hex(self._compute_root(0, len(self._leaves)))

    def add_leaf(self, data: bytes) -> None:
        self._leaves.append(_leaf_hash(data))

    def snapshot(self) -> dict[str, Any]:
        return {"root": self.root, "leaf_count": self.leaf_count}

    # --- Inclusion proofs ---

    def inclusion_proof(self, index: int) -> list[dict[str, Any]]:
        if index < 0 or index >= len(self._leaves):
            raise IndexError(f"Leaf index {index} out of range [0, {len(self._leaves)})")
        path: list[dict[str, Any]] = []
        self._build_inclusion_path(index, 0, len(self._leaves), path)
        return path

    def verify_inclusion(self, index: int, data: bytes, proof: list[dict[str, Any]],
                         expected_root: str | None = None) -> bool:
        return self.verify_inclusion_static(data, proof, expected_root or self.root)

    @staticmethod
    def verify_inclusion_static(data: bytes, proof: list[dict[str, Any]],
                                expected_root: str) -> bool:
        current = _leaf_hash(data)
        for step in proof:
            sibling = bytes.fromhex(step["hash"])
            if step["side"] == "left":
                current = _node_hash(sibling, current)
            else:
                current = _node_hash(current, sibling)
        return _hex(current) == expected_root

    # --- Consistency proofs ---

    def consistency_proof(self, old_size: int) -> list[bytes]:
        if old_size < 0 or old_size > len(self._leaves):
            raise ValueError(f"old_size {old_size} out of range")
        if old_size == 0 or old_size == len(self._leaves):
            return []
        return self._subproof(old_size, 0, len(self._leaves), True)

    def _subproof(self, m: int, lo: int, hi: int, start: bool) -> list[bytes]:
        """RFC 6962 §2.1.4 SUBPROOF(m, D[lo:hi], start)."""
        n = hi - lo
        if m == n:
            if not start:
                return [self._compute_root(lo, hi)]
            return []
        if m == 0:
            return [self._compute_root(lo, hi)]
        k = _largest_power_of_2_less_than(n)
        if m <= k:
            return (self._subproof(m, lo, lo + k, start)
                    + [self._compute_root(lo + k, hi)])
        else:
            return (self._subproof(m - k, lo + k, hi, False)
                    + [self._compute_root(lo, lo + k)])

    @staticmethod
    def verify_consistency_static(
        old_root: str, old_size: int, new_root: str, new_size: int,
        proof: list[bytes]
    ) -> bool:
        """Verify a consistency proof between two tree sizes.

        Uses the verification algorithm from RFC 6962 §2.1.4, matching
        the SUBPROOF generation structure.
        """
        if old_size == 0:
            return True
        if old_size == new_size:
            return old_root == new_root and len(proof) == 0
        if not proof:
            return False
        try:
            old_hash, new_hash = _verify_consistency(
                old_size, new_size, proof, _unhex(old_root)
            )
        except (IndexError, ValueError):
            return False
        return _hex(old_hash) == old_root and _hex(new_hash) == new_root

    # --- Internal tree computation ---

    def _compute_root(self, lo: int, hi: int) -> bytes:
        n = hi - lo
        if n == 1:
            return self._leaves[lo]
        split = _largest_power_of_2_less_than(n)
        left = self._compute_root(lo, lo + split)
        right = self._compute_root(lo + split, hi)
        return _node_hash(left, right)

    def _build_inclusion_path(
        self, index: int, lo: int, hi: int, path: list[dict[str, Any]]
    ) -> None:
        n = hi - lo
        if n == 1:
            return
        split = _largest_power_of_2_less_than(n)
        if index - lo < split:
            self._build_inclusion_path(index, lo, lo + split, path)
            right = self._compute_root(lo + split, hi)
            path.append({"hash": right.hex(), "side": "right"})
        else:
            self._build_inclusion_path(index, lo + split, hi, path)
            left = self._compute_root(lo, lo + split)
            path.append({"hash": left.hex(), "side": "left"})


def _verify_consistency(
    old_size: int, new_size: int, proof: list[bytes], old_root_bytes: bytes
) -> tuple[bytes, bytes]:
    """Verify consistency proof by replaying the SUBPROOF structure.

    The proof is generated by SUBPROOF(m, D[0:n], b=True). We replay the
    same recursive decomposition, consuming proof elements in order, and
    reconstruct both old_hash and new_hash.

    When the subproof hits m==n with start=True (emitting no element),
    the hash is the old tree root which the verifier already knows.
    """
    idx_box = [0]

    def consume() -> bytes:
        i = idx_box[0]
        if i >= len(proof):
            raise IndexError("proof too short")
        idx_box[0] = i + 1
        return proof[i]

    def walk(m: int, n: int, start: bool) -> tuple[bytes, bytes]:
        """Returns (old_hash_contribution, new_hash_contribution).

        For subtrees entirely within the old tree (m==n, start=True),
        old_hash == new_hash == the known old subtree root. Since the
        subproof emits nothing here, we use old_root_bytes which the
        verifier supplies. This works because when start=True and m==n,
        it only occurs once at the deepest left recursion, and that
        subtree IS the old tree root.
        """
        if m == n:
            if not start:
                p = consume()
                return (p, p)
            # start=True, m==n: this subtree is exactly the old tree.
            # No proof element. Use the claimed old root.
            return (old_root_bytes, old_root_bytes)
        if m == 0:
            # This subtree is entirely new; doesn't affect old hash.
            p = consume()
            return (None, p)  # type: ignore[return-value]
        k = _largest_power_of_2_less_than(n)
        if m <= k:
            old_left, new_left = walk(m, k, start)
            right_hash = consume()
            new_combined = _node_hash(new_left, right_hash)
            return (old_left, new_combined)
        else:
            old_right, new_right = walk(m - k, n - k, False)
            left_hash = consume()
            new_combined = _node_hash(left_hash, new_right)
            old_combined = _node_hash(left_hash, old_right)
            return (old_combined, new_combined)

    old_hash, new_hash = walk(old_size, new_size, True)
    if idx_box[0] != len(proof):
        raise ValueError(f"proof has extra elements: used {idx_box[0]} of {len(proof)}")
    return old_hash, new_hash
