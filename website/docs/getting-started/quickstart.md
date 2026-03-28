---
title: Quickstart
description: Build and run an ANIP service, then inspect it with curl and Studio.
---

# Quickstart

Build a working ANIP service in Python, run it, and explore all 9 protocol endpoints.

## Prerequisites

- Python 3.11+
- pip

## 1. Install

```bash
pip install anip-service anip-fastapi uvicorn
```

## 2. Create your service

Create `app.py`:

```python
from fastapi import FastAPI
from anip_service import ANIPService, Capability
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SideEffect, SideEffectType
from anip_fastapi import mount_anip

# Business logic — ANIP-free
def do_search(origin, destination):
    return [
        {"flight_number": "AA100", "origin": origin, "destination": destination, "price": 420},
        {"flight_number": "DL310", "origin": origin, "destination": destination, "price": 280},
    ]

# Capability declaration — tells agents what this does before they call it
search_flights = Capability(
    declaration=CapabilityDeclaration(
        name="search_flights",
        description="Search available flights between airports",
        contract_version="1.0",
        inputs=[
            CapabilityInput(name="origin", type="airport_code", description="Departure airport"),
            CapabilityInput(name="destination", type="airport_code", description="Arrival airport"),
        ],
        output=CapabilityOutput(type="flight_list", fields=["flight_number", "price"]),
        side_effect=SideEffect(type=SideEffectType.READ),
        minimum_scope=["travel.search"],
    ),
    handler=lambda ctx, params: {"flights": do_search(params["origin"], params["destination"])},
)

# Service setup
service = ANIPService(
    service_id="quickstart-flights",
    capabilities=[search_flights],
    storage="sqlite:///quickstart.db",
    trust="signed",
    authenticate=lambda bearer: {"demo-key": "human:demo@example.com"}.get(bearer),
)

app = FastAPI()
mount_anip(app, service)
```

## 3. Run it

```bash
uvicorn app:app --port 9100
```

## 4. Explore the protocol

Now use curl to walk through each ANIP endpoint:

### Discovery

```bash
curl http://localhost:9100/.well-known/anip | python -m json.tool
```

```json
{
  "anip_discovery": {
    "version": "0.11.0",
    "service_id": "quickstart-flights",
    "endpoints": {
      "manifest": "/anip/manifest",
      "tokens": "/anip/tokens",
      "permissions": "/anip/permissions",
      "invoke": "/anip/invoke/{capability}",
      "audit": "/anip/audit",
      "checkpoints": "/anip/checkpoints"
    },
    "capabilities": {
      "search_flights": {
        "side_effect": { "type": "read" },
        "minimum_scope": ["travel.search"]
      }
    },
    "trust": { "level": "signed" }
  }
}
```

### Issue a delegation token

```bash
curl -X POST http://localhost:9100/anip/tokens \
  -H "Authorization: Bearer demo-key" \
  -H "Content-Type: application/json" \
  -d '{"scope": ["travel.search"], "capability": "search_flights"}'
```

```json
{
  "issued": true,
  "token": "eyJhbGciOi...",
  "scope": ["travel.search"],
  "capability": "search_flights"
}
```

### Check permissions

```bash
curl -X POST http://localhost:9100/anip/permissions \
  -H "Authorization: Bearer <token-from-above>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

```json
{
  "available": [
    { "capability": "search_flights", "scope_match": "travel.search" }
  ],
  "restricted": [],
  "denied": []
}
```

### Invoke a capability

```bash
curl -X POST http://localhost:9100/anip/invoke/search_flights \
  -H "Authorization: Bearer <token-from-above>" \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"origin": "SEA", "destination": "SFO"}}'
```

```json
{
  "success": true,
  "invocation_id": "inv_7f3a2b...",
  "result": {
    "flights": [
      { "flight_number": "AA100", "origin": "SEA", "destination": "SFO", "price": 420 },
      { "flight_number": "DL310", "origin": "SEA", "destination": "SFO", "price": 280 }
    ]
  }
}
```

### Query audit log

```bash
curl -X POST http://localhost:9100/anip/audit \
  -H "Authorization: Bearer demo-key" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Every invocation is automatically logged with the capability name, caller identity, event classification, and timestamp.

## 5. Open Studio

For a visual experience, add the Studio adapter:

```bash
pip install anip-studio
```

Add one line to your `app.py`:

```python
from anip_studio import mount_anip_studio
mount_anip_studio(app, service)
```

Open [http://localhost:9100/studio/](http://localhost:9100/studio/) to browse discovery, manifest, JWKS, audit, checkpoints, and invoke capabilities through a UI.

## What to notice

- **Discovery** tells the agent what the service offers before any authentication
- **The manifest** is signed — the agent can cryptographically verify the service's claims haven't been tampered with
- **Tokens** are scoped — the agent gets exactly the authority it needs, nothing more
- **Permissions** are checkable before invoke — no more "try and see what happens"
- **Failures** include structured recovery guidance, not just error codes
- **Audit** is automatic and queryable — every action is recorded

## Next steps

- **[Install](/docs/getting-started/install)** — Package install commands for TypeScript, Java, Go, C#
- **[Capability Declaration](/docs/protocol/capabilities)** — Deep dive into how capabilities work
- **[Studio & Showcases](/docs/getting-started/studio-showcases)** — Run the full showcase apps
