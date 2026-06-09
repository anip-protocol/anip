# ANIP Registry: Go Service and Thin Web UI Plan

## Purpose

ANIP Registry is a separate infrastructure product.

It must not be implemented as an internal Studio-only feature, and it should not use Python or a TypeScript server as the trusted core.

The trusted core should be a small Go service that owns:

- immutable published records
- package/version resolution
- registry receipts
- publish-time validation
- signature and digest verification

The web UI is a convenience layer.

It can be implemented in TypeScript, but it must not be the trust anchor.

## Architecture

### Trusted Core

Go backend service.

Responsibilities:

- accept selected lineage publication requests
- validate immutable publish inputs
- persist published lineage and package records
- issue registry receipts
- resolve package/version identities
- expose publication/package/receipt APIs

### Thin UI

TypeScript frontend.

Responsibilities:

- browse published packages
- inspect package/version details
- inspect receipts and provenance
- later trigger publication flows through Studio or privileged tools

### External Integrations

- Studio publishes selected revisions over HTTP
- generator resolves published identities from Registry
- verifier resolves published identities from Registry

## Phase 1 Deliverables

Phase 1 should produce a real service boundary, even if the internal storage model remains minimal.

Deliver:

1. Go registry backend scaffold
2. Thin TS registry UI scaffold
3. Minimal HTTP API:
   - health
   - list publications
   - get package/version
   - get receipt
4. Runnable backend binary
5. Clear repo boundary for later persistence and auth work

## Repo Placement

### Backend

- `packages/go/registryapi`
- `packages/go/cmd/anip-registry`

### Frontend

- `registry/`

This keeps the trusted backend in Go and the UI as a separate web app from day one.

## Initial API

Base prefix:

- `/registry-api/v1`

Routes:

- `GET /registry-api/v1/healthz`
- `GET /registry-api/v1/publications`
- `GET /registry-api/v1/packages/{packageId}/{version}`
- `GET /registry-api/v1/packages/{packageId}/{version}/receipt`

Phase 1 publication writes can be added next as:

- `POST /registry-api/v1/publications`

but the first scaffold does not need to expose mutation immediately if it would force premature persistence design.

## Data Shape

Even the scaffold should model the real published concepts:

- `PublicationSummary`
- `RegistryPackageRecord`
- `RegistryReceipt`

These types should already carry:

- package id
- package version
- project ref
- product revision ref
- developer revision ref
- contract signature
- published at

## Security Direction

The main security principle is minimizing the trusted computing base.

The backend service should keep dependencies small and own:

- digest calculation
- receipt generation
- publication immutability checks
- package resolution semantics

The frontend should never be treated as authoritative.

## Immediate Implementation Steps

1. Add Go `registryapi` package with minimal in-memory store and HTTP handlers.
2. Add runnable `anip-registry` command.
3. Add TS `registry/` frontend with list/detail routes.
4. Point the frontend at `/registry-api`.
5. Add backend tests for list/detail/receipt endpoints.

## Next Step After Scaffold

The next implementation phase after this scaffold is:

- persistent storage
- publication endpoint
- Studio publish integration
- generator/verifier registry resolution
