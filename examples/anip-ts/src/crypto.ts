/**
 * Key management and cryptographic operations for ANIP v0.2.
 *
 * Uses the `jose` library for ES256 JWT signing/verification and JWS detached signatures.
 * Manages two key pairs: one for delegation tokens, one for audit entry signing.
 */

import * as jose from "jose";
import { readFileSync, writeFileSync, existsSync } from "fs";
import { createHash } from "crypto";

interface PersistedKeys {
  delegationJwk: jose.JWK;
  delegationKid: string;
  auditJwk: jose.JWK;
  auditKid: string;
}

export class KeyManager {
  private privateKey!: CryptoKey;
  private publicKey!: CryptoKey;
  private kid!: string;
  private auditPrivateKey!: CryptoKey;
  private auditPublicKey!: CryptoKey;
  private auditKid!: string;
  private _ready: Promise<void>;

  constructor(keyPath?: string) {
    this._ready = this.init(keyPath);
  }

  private async init(keyPath?: string) {
    if (keyPath && existsSync(keyPath)) {
      await this.loadKeys(keyPath);
      return;
    }

    // Generate delegation key pair (extractable so we can persist)
    const { publicKey, privateKey } = await jose.generateKeyPair("ES256", {
      extractable: true,
    });
    this.privateKey = privateKey as CryptoKey;
    this.publicKey = publicKey as CryptoKey;
    const jwk = await jose.exportJWK(this.publicKey);
    this.kid = await this.computeKid(jwk);

    // Generate audit key pair (separate from delegation)
    const audit = await jose.generateKeyPair("ES256", {
      extractable: true,
    });
    this.auditPrivateKey = audit.privateKey as CryptoKey;
    this.auditPublicKey = audit.publicKey as CryptoKey;
    const auditJwk = await jose.exportJWK(this.auditPublicKey);
    this.auditKid = await this.computeKid(auditJwk);

    if (keyPath) {
      await this.saveKeys(keyPath);
    }
  }

  private async saveKeys(path: string) {
    const delegationJwk = await jose.exportJWK(this.privateKey);
    const auditJwk = await jose.exportJWK(this.auditPrivateKey);
    writeFileSync(
      path,
      JSON.stringify({
        delegationJwk,
        delegationKid: this.kid,
        auditJwk,
        auditKid: this.auditKid,
      } as PersistedKeys)
    );
  }

  private async loadKeys(path: string) {
    const data: PersistedKeys = JSON.parse(readFileSync(path, "utf-8"));
    this.kid = data.delegationKid;
    this.privateKey = (await jose.importJWK(
      data.delegationJwk,
      "ES256"
    )) as CryptoKey;
    this.publicKey = (await jose.importJWK(
      { ...data.delegationJwk, d: undefined },
      "ES256"
    )) as CryptoKey;
    this.auditKid = data.auditKid;
    this.auditPrivateKey = (await jose.importJWK(
      data.auditJwk,
      "ES256"
    )) as CryptoKey;
    this.auditPublicKey = (await jose.importJWK(
      { ...data.auditJwk, d: undefined },
      "ES256"
    )) as CryptoKey;
  }

  private async computeKid(jwk: jose.JWK): Promise<string> {
    const thumbprint = await jose.calculateJwkThumbprint(jwk);
    return thumbprint.slice(0, 16);
  }

  async ready(): Promise<void> {
    return this._ready;
  }

  async getJWKS(): Promise<{ keys: jose.JWK[] }> {
    await this._ready;
    const delegationJwk = await jose.exportJWK(this.publicKey);
    const auditJwk = await jose.exportJWK(this.auditPublicKey);
    return {
      keys: [
        { ...delegationJwk, kid: this.kid, alg: "ES256", use: "sig" },
        { ...auditJwk, kid: this.auditKid, alg: "ES256", use: "audit" },
      ],
    };
  }

  async signJWT(payload: jose.JWTPayload): Promise<string> {
    await this._ready;
    return new jose.SignJWT(payload)
      .setProtectedHeader({ alg: "ES256", kid: this.kid })
      .sign(this.privateKey);
  }

  async verifyJWT(token: string): Promise<jose.JWTPayload> {
    await this._ready;
    const { payload } = await jose.jwtVerify(token, this.publicKey, {
      algorithms: ["ES256"],
    });
    return payload;
  }

  async signJWSDetached(payload: Uint8Array): Promise<string> {
    await this._ready;
    const jws = await new jose.CompactSign(payload)
      .setProtectedHeader({ alg: "ES256", kid: this.kid })
      .sign(this.privateKey);
    const [header, , signature] = jws.split(".");
    return `${header}..${signature}`;
  }

  async signJWSDetachedAudit(payload: Uint8Array): Promise<string> {
    await this._ready;
    const jws = await new jose.CompactSign(payload)
      .setProtectedHeader({ alg: "ES256", kid: this.auditKid })
      .sign(this.auditPrivateKey);
    const [header, , signature] = jws.split(".");
    return `${header}..${signature}`;
  }

  async signAuditEntry(
    entryData: Record<string, unknown>
  ): Promise<string> {
    await this._ready;
    const filtered = Object.fromEntries(
      Object.entries(entryData)
        .filter(([k]) => k !== "signature" && k !== "id")
        .sort(([a], [b]) => a.localeCompare(b))
    );
    const canonical = JSON.stringify(filtered);
    const hash = createHash("sha256").update(canonical).digest("hex");
    return new jose.SignJWT({ audit_hash: hash })
      .setProtectedHeader({ alg: "ES256", kid: this.auditKid })
      .sign(this.auditPrivateKey);
  }
}
