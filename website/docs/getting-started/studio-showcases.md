---
title: Studio and Showcases
description: The easiest way to see ANIP's features in a realistic service.
---

# Studio and Showcases

ANIP ships with three showcase domains:

- travel
- finance
- DevOps

These are not toy one-endpoint demos. They exercise:

- read vs write vs irreversible operations
- permission discovery
- cost signaling
- structured failures
- audit and checkpoints
- Studio inspection and invocation

## Studio

ANIP Studio lets you inspect and invoke ANIP services visually.

Current capabilities:

- discovery inspection
- manifest and capability review
- JWKS inspection
- audit browsing
- checkpoint inspection
- invoke view with permissions and failure rendering

Studio runs:

- **embedded** at `/studio`
- **standalone** as a Dockerized static app

## Why start here

If you are evaluating ANIP, Studio plus a showcase app is the fastest path to understanding:

- what the manifest actually looks like
- how side effects and scope are declared
- how permissions change with bearer tokens
- what structured failures look like in practice

## Where to look in the repo

- `examples/showcase/travel/`
- `examples/showcase/finance/`
- `examples/showcase/devops/`
- `studio/`
