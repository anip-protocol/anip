---
title: Studio
description: ANIP Studio is the inspection and invocation console for ANIP services.
---

# Studio

ANIP Studio is the visual front end for ANIP services.

## What it does

Studio lets users inspect:

- discovery
- manifest
- JWKS
- audit
- checkpoints

And invoke capabilities with:

- bearer-based auth context
- permission inspection
- structured failure rendering

## Deployment modes

Studio currently runs in two modes:

- **embedded** inside a Python ANIP service at `/studio`
- **standalone** as a Dockerized static app

This gives ANIP both an embedded operator UI and a standalone evaluation surface.
