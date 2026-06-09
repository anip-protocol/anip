# verifier

verifier foundation for ANIP Service Definition integrity checks.

Current scope:

- resolve an `anip-service-definition.json` from a local file
- resolve an `anip-service-definition.json` from a portable `.anip-package.json` bundle
- resolve an `anip-service-definition.json` from Registry package identity
- recompute the canonical Service Definition digest
- compare Registry `definition_digest` with the locally recomputed digest
- compare Registry `manifest_digest` and `lock_digest` with recomputed digests
- confirm the compiled contract signature is present
- optionally compare an expected compiled contract signature
- confirm the Registry receipt signature is present for Registry-resolved packages
- fetch Registry public keys and verify Ed25519 receipt signatures for Registry-resolved packages
- include Registry signing mode and active key id in JSON output when the Registry exposes them
- support Registry key rotation by selecting the public key matching the receipt key id
- verify bundle manifest digest and deterministic local receipt signature for package-bundle mode

This is the first lineage/integrity layer. Runtime conformance packs and behavior-level verifier packs are separate next steps.

## CLI

Verify a local Service Definition:

```bash
cd packages/go
go run ./cmd/anip validate \
  --definition ./path/to/anip-service-definition.json
```

Verify a Registry package/version:

```bash
cd packages/go
go run ./cmd/anip validate \
  --registry-url http://127.0.0.1:8200 \
  --package issue-tracker-native-and-mcp-fronting@0.1.0
```

Verify a portable Studio-local package bundle without running Studio or Registry:

```bash
cd packages/go
go run ./cmd/anip validate \
  --package-bundle ./work-item-fronting-0.2.0.anip-package.json
```

Pin the expected compiled contract signature:

```bash
cd packages/go
go run ./cmd/anip validate \
  --registry-url http://127.0.0.1:8200 \
  --package issue-tracker-native-and-mcp-fronting@0.1.0 \
  --expected-contract-signature sha256:...
```

Require a production Registry and a specific receipt signing key:

```bash
cd packages/go
go run ./cmd/anip validate \
  --registry-url https://registry.example.com \
  --package issue-tracker-native-and-mcp-fronting@0.1.0 \
  --require-registry-mode production \
  --trusted-registry-key-id registry-prod-2026-04
```

Policy mismatches are emitted as failed JSON checks, so callers can persist the verifier result as audit evidence.

`anip-verify` remains available as a compatibility binary, but `anip validate` is the primary command shape for package managers such as Homebrew. `anip verify` remains a compatibility alias.
