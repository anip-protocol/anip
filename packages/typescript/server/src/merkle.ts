/**
 * RFC 6962 Merkle tree with inclusion and consistency proofs.
 *
 * Port of the Python implementation — produces identical roots for the same
 * input data (protocol interop requirement).
 */
import { createHash } from "crypto";

function sha256(data: Buffer): Buffer {
  return createHash("sha256").update(data).digest();
}

function leafHash(data: Buffer): Buffer {
  return sha256(Buffer.concat([Buffer.from([0x00]), data]));
}

function nodeHash(left: Buffer, right: Buffer): Buffer {
  return sha256(Buffer.concat([Buffer.from([0x01]), left, right]));
}

function hex(digest: Buffer): string {
  return `sha256:${digest.toString("hex")}`;
}

function unhex(s: string): Buffer {
  if (s.startsWith("sha256:")) {
    return Buffer.from(s.slice(7), "hex");
  }
  return Buffer.from(s, "hex");
}

function largestPowerOf2LessThan(n: number): number {
  if (n <= 1) return 0;
  let k = 1;
  while (k * 2 < n) k *= 2;
  return k;
}

export interface InclusionStep {
  hash: string;
  side: "left" | "right";
}

export interface Snapshot {
  root: string;
  leaf_count: number;
}

export class MerkleTree {
  private _leaves: Buffer[] = [];

  get leafCount(): number {
    return this._leaves.length;
  }

  get root(): string {
    if (this._leaves.length === 0) {
      return hex(sha256(Buffer.alloc(0)));
    }
    return hex(this._computeRoot(0, this._leaves.length));
  }

  addLeaf(data: Buffer): void {
    this._leaves.push(leafHash(data));
  }

  snapshot(): Snapshot {
    return { root: this.root, leaf_count: this.leafCount };
  }

  // --- Inclusion proofs ---

  inclusionProof(index: number): InclusionStep[] {
    if (index < 0 || index >= this._leaves.length) {
      throw new RangeError(
        `Leaf index ${index} out of range [0, ${this._leaves.length})`
      );
    }
    const path: InclusionStep[] = [];
    this._buildInclusionPath(index, 0, this._leaves.length, path);
    return path;
  }

  verifyInclusion(
    index: number,
    data: Buffer,
    proof: InclusionStep[],
    expectedRoot?: string
  ): boolean {
    return MerkleTree.verifyInclusionStatic(
      data,
      proof,
      expectedRoot ?? this.root
    );
  }

  static verifyInclusionStatic(
    data: Buffer,
    proof: InclusionStep[],
    expectedRoot: string
  ): boolean {
    let current = leafHash(data);
    for (const step of proof) {
      const sibling = Buffer.from(step.hash, "hex");
      if (step.side === "left") {
        current = nodeHash(sibling, current);
      } else {
        current = nodeHash(current, sibling);
      }
    }
    return hex(current) === expectedRoot;
  }

  // --- Consistency proofs ---

  consistencyProof(oldSize: number): Buffer[] {
    if (oldSize < 0 || oldSize > this._leaves.length) {
      throw new RangeError(`oldSize ${oldSize} out of range`);
    }
    if (oldSize === 0 || oldSize === this._leaves.length) {
      return [];
    }
    return this._subproof(oldSize, 0, this._leaves.length, true);
  }

  verifyConsistency(
    oldRoot: string,
    oldSize: number,
    proof: Buffer[]
  ): boolean {
    return MerkleTree.verifyConsistencyStatic(
      oldRoot,
      oldSize,
      this.root,
      this.leafCount,
      proof
    );
  }

  static verifyConsistencyStatic(
    oldRoot: string,
    oldSize: number,
    newRoot: string,
    newSize: number,
    proof: Buffer[]
  ): boolean {
    if (oldSize === 0) return true;
    if (oldSize === newSize) return oldRoot === newRoot && proof.length === 0;
    if (proof.length === 0) return false;
    try {
      const [oldHash, newHash] = verifyConsistency(
        oldSize,
        newSize,
        proof,
        unhex(oldRoot)
      );
      return hex(oldHash) === oldRoot && hex(newHash) === newRoot;
    } catch {
      return false;
    }
  }

  // --- Internal tree computation ---

  private _computeRoot(lo: number, hi: number): Buffer {
    const n = hi - lo;
    if (n === 1) return this._leaves[lo];
    const split = largestPowerOf2LessThan(n);
    const left = this._computeRoot(lo, lo + split);
    const right = this._computeRoot(lo + split, hi);
    return nodeHash(left, right);
  }

  private _buildInclusionPath(
    index: number,
    lo: number,
    hi: number,
    path: InclusionStep[]
  ): void {
    const n = hi - lo;
    if (n === 1) return;
    const split = largestPowerOf2LessThan(n);
    if (index - lo < split) {
      this._buildInclusionPath(index, lo, lo + split, path);
      const right = this._computeRoot(lo + split, hi);
      path.push({ hash: right.toString("hex"), side: "right" });
    } else {
      this._buildInclusionPath(index, lo + split, hi, path);
      const left = this._computeRoot(lo, lo + split);
      path.push({ hash: left.toString("hex"), side: "left" });
    }
  }

  private _subproof(
    m: number,
    lo: number,
    hi: number,
    start: boolean
  ): Buffer[] {
    const n = hi - lo;
    if (m === n) {
      if (!start) return [this._computeRoot(lo, hi)];
      return [];
    }
    if (m === 0) {
      return [this._computeRoot(lo, hi)];
    }
    const k = largestPowerOf2LessThan(n);
    if (m <= k) {
      return [
        ...this._subproof(m, lo, lo + k, start),
        this._computeRoot(lo + k, hi),
      ];
    } else {
      return [
        ...this._subproof(m - k, lo + k, hi, false),
        this._computeRoot(lo, lo + k),
      ];
    }
  }
}

// --- Consistency proof verification (standalone) ---

function verifyConsistency(
  oldSize: number,
  newSize: number,
  proof: Buffer[],
  oldRootBytes: Buffer
): [Buffer, Buffer] {
  let idx = 0;

  function consume(): Buffer {
    if (idx >= proof.length) throw new RangeError("proof too short");
    return proof[idx++];
  }

  function walk(
    m: number,
    n: number,
    start: boolean
  ): [Buffer, Buffer] {
    if (m === n) {
      if (!start) {
        const p = consume();
        return [p, p];
      }
      return [oldRootBytes, oldRootBytes];
    }
    if (m === 0) {
      const p = consume();
      return [null as unknown as Buffer, p];
    }
    const k = largestPowerOf2LessThan(n);
    if (m <= k) {
      const [oldLeft, newLeft] = walk(m, k, start);
      const rightHash = consume();
      const newCombined = nodeHash(newLeft, rightHash);
      return [oldLeft, newCombined];
    } else {
      const [oldRight, newRight] = walk(m - k, n - k, false);
      const leftHash = consume();
      const newCombined = nodeHash(leftHash, newRight);
      const oldCombined = nodeHash(leftHash, oldRight);
      return [oldCombined, newCombined];
    }
  }

  const [oldHash, newHash] = walk(oldSize, newSize, true);
  if (idx !== proof.length) {
    throw new Error(`proof has extra elements: used ${idx} of ${proof.length}`);
  }
  return [oldHash, newHash];
}
