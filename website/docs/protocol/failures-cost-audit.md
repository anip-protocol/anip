---
title: Failures, Cost, and Audit
description: ANIP failures, cost signaling, and audit posture make execution operationally useful.
---

# Failures, Cost, and Audit

ANIP does not stop at "success or error."

It makes three execution surfaces much more useful to agents:

## Structured failures

ANIP failures can include:

- failure type
- human-readable detail
- resolution guidance
- grantable authority hints
- retry hints

This makes failures actionable instead of merely descriptive.

## Cost signaling

ANIP lets services declare cost expectations and return actual cost after execution.

That matters for:

- financial operations
- budget-bound delegation
- ranking alternatives before invoke

## Audit posture

ANIP also standardizes what is logged, how long it is retained, and what the service exposes for later review.

In higher-trust environments, this is as important as the invoke response itself.
