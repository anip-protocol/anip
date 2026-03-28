---
title: Quickstart
description: The smallest practical way to run ANIP and inspect it.
---

# Quickstart

The fastest way to understand ANIP is to run a real service and inspect it.

## Python quickstart

```python
from fastapi import FastAPI
from anip_service import ANIPService, Capability
from anip_fastapi import mount_anip

def search_flights(origin: str, destination: str):
    return {
        "flights": [
            {"flight_number": "AA100", "origin": origin, "destination": destination, "price": 420},
            {"flight_number": "DL310", "origin": origin, "destination": destination, "price": 280},
        ]
    }

service = ANIPService(
    service_id="quickstart-travel",
    capabilities=[
        Capability(
            name="search_flights",
            description="Search available flights",
            side_effect="read",
            scope=["travel.search"],
            handler=search_flights,
        ),
    ],
    authenticate=lambda bearer: {"demo-human-key": "human:demo@example.com"}.get(bearer),
)

app = FastAPI()
mount_anip(app, service)
```

## What to inspect first

Once the service is running:

1. `GET /.well-known/anip`
2. `GET /anip/manifest`
3. `POST /anip/tokens`
4. `POST /anip/permissions`
5. `POST /anip/invoke/search_flights`

## What to notice

- discovery tells you the service shape
- manifest tells you the capability contract
- token issuance scopes authority
- permissions tell you what is available before invoke
- invoke returns structured success or failure

## Better first-run path

If you want a fuller experience, run one of the showcase apps and open Studio:

- [Studio and Showcases](./studio-showcases.md)
