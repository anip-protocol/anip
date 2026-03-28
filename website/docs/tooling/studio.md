---
title: Studio
description: ANIP Studio is the inspection and invocation UI for ANIP services.
---

# ANIP Studio

Studio is a browser-based UI for inspecting and interacting with ANIP services. Connect to any ANIP service and browse its discovery document, manifest, keys, audit log, and checkpoints — then invoke capabilities with permissions checking and structured failure display.

## Views

| View | What it shows |
|------|---------------|
| **Discovery** | Protocol version, service identity, capability summary, trust posture, endpoints |
| **Manifest** | Full capability declarations — side effects, costs, scopes, inputs/outputs, signature |
| **JWKS** | Public signing keys for manifest and token verification |
| **Audit** | Browsable audit entries with filtering by capability, event class, time range |
| **Checkpoints** | Merkle checkpoint list with detail inspection |
| **Invoke** | Form-based capability invocation with permissions panel and structured result/failure rendering |

## Deployment modes

### Embedded

Mount Studio inside your Python ANIP service at `/studio`:

```python
from anip_studio import mount_anip_studio

mount_anip_studio(app, service)
# → Open http://localhost:9100/studio/
```

In embedded mode, Studio auto-connects to the host service. No CORS needed.

### Standalone (Docker)

Run Studio as an independent container that connects to any ANIP service:

```bash
docker build -t anip-studio studio/
docker run -p 3000:80 anip-studio
# → Open http://localhost:3000, enter service URL
```

Standalone Studio requires the target ANIP service to have CORS enabled (see [HTTP transport: CORS](/docs/transports/http#cors)).

## Invoke workflow

Studio's Invoke view walks through the same agent workflow the protocol defines:

1. **Select capability** — pick from the manifest or deep-link from a capability card
2. **Auth** — enter a bearer token (API key or delegation token)
3. **Permissions** — auto-checks what the token allows (available / restricted / denied)
4. **Input form** — generated from the manifest's input declarations with type hints and defaults
5. **Result** — success with `invocation_id`, `cost_actual`, and result data, or structured failure with resolution guidance
