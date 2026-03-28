---
title: Checkpoints and Trust
description: Signed manifests, JWKS, checkpoints, and trust posture extend ANIP beyond simple tool metadata.
---

# Checkpoints and Trust

ANIP includes a trust story, not just a tool schema.

## Signed artifacts

ANIP services can expose:

- signed manifests
- JWKS for verification
- signed audit and checkpoint evidence

JWKS is the verification surface for those service-signed artifacts. It is not the trust anchor by itself.

## Audit checkpoints

ANIP can produce Merkle checkpoints over audit history, allowing later verification that execution evidence was recorded and not silently rewritten.

## Trust posture

Discovery exposes trust posture so callers can understand whether a service is:

- declarative only
- signed
- anchored
- or moving toward stronger attestation models

This lets agents and operators adjust how much they rely on service claims.
