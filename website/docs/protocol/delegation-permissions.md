---
title: Delegation and Permissions
description: ANIP separates who is acting, on whose behalf, and what authority is available.
---

# Delegation and Permissions

ANIP uses structured delegation rather than treating every bearer token as a flat capability blob.

## Delegation

Delegation answers:

- who is asking
- on whose behalf
- with what scoped authority
- under what budget or purpose constraints

This is represented through ANIP tokens and the delegation chain model.

## Permission discovery

Permission discovery is a first-class ANIP primitive.

Before invoking a capability, a caller can ask:

- what is available
- what is restricted
- what is denied

That is materially different from discovering permission only after an invoke fails.

## Why this matters

It lets agents:

- plan before acting
- explain why something is blocked
- request additional authority intentionally
- avoid destructive trial-and-error
