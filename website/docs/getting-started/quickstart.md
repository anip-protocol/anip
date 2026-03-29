---
title: Quickstart
description: Build and run an ANIP service, then inspect it with curl and Studio.
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Quickstart

Build a working ANIP service, run it, and explore all 9 protocol endpoints.

## 1. Install

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

**Prerequisites:** Python 3.11+

```bash
pip install anip-service anip-fastapi uvicorn
```

</TabItem>
<TabItem value="typescript" label="TypeScript">

**Prerequisites:** Node.js 20+

```bash
npm install @anip-dev/service @anip-dev/hono
```

</TabItem>
<TabItem value="go" label="Go">

**Prerequisites:** Go 1.22+

```bash
go get github.com/anip-protocol/anip/packages/go
```

</TabItem>
<TabItem value="java" label="Java">

**Prerequisites:** Java 21+, Maven

```xml
<dependency>
  <groupId>dev.anip</groupId>
  <artifactId>anip-service</artifactId>
  <version>0.11.0</version>
</dependency>
<dependency>
  <groupId>dev.anip</groupId>
  <artifactId>anip-spring-boot</artifactId>
  <version>0.11.0</version>
</dependency>
```

</TabItem>
<TabItem value="csharp" label="C#">

**Prerequisites:** .NET 8+

C# packages are available in-repo (NuGet publishing coming soon):

```bash
# From the ANIP repo root:
dotnet add reference packages/csharp/src/Anip.Service
dotnet add reference packages/csharp/src/Anip.AspNetCore
```

</TabItem>
</Tabs>

## 2. Create your service

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

Create `app.py`:

```python
from fastapi import FastAPI
from anip_service import ANIPService, Capability
from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    SideEffect, SideEffectType,
)
from anip_fastapi import mount_anip

# Business logic — ANIP-free
def do_search(origin, destination):
    return [
        {"flight_number": "AA100", "origin": origin, "destination": destination, "price": 420},
        {"flight_number": "DL310", "origin": origin, "destination": destination, "price": 280},
    ]

# Capability declaration
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

Run it:

```bash
uvicorn app:app --port 9100
```

</TabItem>
<TabItem value="typescript" label="TypeScript">

Create `app.ts`:

```typescript
import { Hono } from "hono";
import { createANIPService, defineCapability } from "@anip-dev/service";
import { mountAnip } from "@anip-dev/hono";

// Business logic — ANIP-free
function doSearch(origin: string, destination: string) {
  return [
    { flight_number: "AA100", origin, destination, price: 420 },
    { flight_number: "DL310", origin, destination, price: 280 },
  ];
}

// Capability declaration
const searchFlights = defineCapability({
  name: "search_flights",
  description: "Search available flights between airports",
  contractVersion: "1.0",
  inputs: [
    { name: "origin", type: "airport_code", description: "Departure airport" },
    { name: "destination", type: "airport_code", description: "Arrival airport" },
  ],
  output: { type: "flight_list", fields: ["flight_number", "price"] },
  sideEffect: { type: "read" },
  minimumScope: ["travel.search"],
  handler: async (ctx, params) => ({
    flights: doSearch(params.origin, params.destination),
  }),
});

// Service setup
const service = createANIPService({
  serviceId: "quickstart-flights",
  capabilities: [searchFlights],
  storage: { type: "sqlite", path: "quickstart.db" },
  trust: "signed",
  authenticate: (bearer) =>
    ({ "demo-key": "human:demo@example.com" })[bearer] ?? null,
});

const app = new Hono();
mountAnip(app, service);
export default { port: 9100, fetch: app.fetch };
```

Run it:

```bash
npx tsx app.ts
```

</TabItem>
<TabItem value="go" label="Go">

Create `main.go`:

```go
package main

import (
    "net/http"
    "github.com/anip-protocol/anip/packages/go/service"
    "github.com/anip-protocol/anip/packages/go/httpapi"
)

func searchFlights() service.CapabilityDef {
    return service.CapabilityDef{
        Name:        "search_flights",
        Description: "Search available flights between airports",
        SideEffect:  "read",
        Scope:       []string{"travel.search"},
        Handler: func(ctx service.InvokeContext, params map[string]any) (any, error) {
            return map[string]any{
                "flights": []map[string]any{
                    {"flight_number": "AA100", "price": 420},
                    {"flight_number": "DL310", "price": 280},
                },
            }, nil
        },
    }
}

func main() {
    svc, _ := service.New(service.Config{
        ServiceID:    "quickstart-flights",
        Capabilities: []service.CapabilityDef{searchFlights()},
        Storage:      "sqlite:///quickstart.db",
        Trust:        "signed",
        Authenticate: func(bearer string) *string {
            keys := map[string]string{"demo-key": "human:demo@example.com"}
            if p, ok := keys[bearer]; ok { return &p }
            return nil
        },
    })
    defer svc.Shutdown()
    svc.Start()

    mux := http.NewServeMux()
    httpapi.MountANIP(mux, svc)
    http.ListenAndServe(":9100", mux)
}
```

Run it:

```bash
go run main.go
```

</TabItem>
<TabItem value="java" label="Java">

Create `Application.java`:

```java
@SpringBootApplication
public class Application {

    @Bean
    public ANIPService anipService() {
        return new ANIPService(new ServiceConfig()
            .setServiceId("quickstart-flights")
            .setCapabilities(List.of(searchFlightsCapability()))
            .setStorage("sqlite:///quickstart.db")
            .setTrust("signed")
            .setAuthenticate(bearer -> {
                var keys = Map.of("demo-key", "human:demo@example.com");
                return Optional.ofNullable(keys.get(bearer));
            }));
    }

    @Bean
    public AnipController anipController(ANIPService svc) {
        return new AnipController(svc);
    }

    static CapabilityDef searchFlightsCapability() {
        return new CapabilityDef()
            .setName("search_flights")
            .setDescription("Search available flights")
            .setSideEffect("read")
            .setScope(List.of("travel.search"))
            .setHandler((ctx, params) -> Map.of(
                "flights", List.of(
                    Map.of("flight_number", "AA100", "price", 420),
                    Map.of("flight_number", "DL310", "price", 280)
                )
            ));
    }
}
```

Run it:

```bash
mvn spring-boot:run
```

</TabItem>
<TabItem value="csharp" label="C#">

Create `Program.cs`:

```csharp
var builder = WebApplication.CreateBuilder(args);

var service = new AnipService(new ServiceConfig {
    ServiceId = "quickstart-flights",
    Capabilities = [SearchFlightsCapability.Create()],
    Storage = "sqlite:///quickstart.db",
    Trust = "signed",
    Authenticate = bearer => {
        var keys = new Dictionary<string, string> {
            ["demo-key"] = "human:demo@example.com"
        };
        return keys.TryGetValue(bearer, out var p) ? p : null;
    }
});

builder.Services.AddAnip(service);
var app = builder.Build();
app.MapControllers();
app.Run("http://localhost:9100");
```

Run it:

```bash
dotnet run
```

</TabItem>
</Tabs>

## 3. Explore the protocol

Now use curl to walk through each ANIP endpoint. These commands work the same regardless of which runtime you chose above.

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

## 4. Open Studio

For a visual experience, add the Studio adapter:

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

```bash
pip install anip-studio
```

Add one line to your `app.py`:

```python
from anip_studio import mount_anip_studio
mount_anip_studio(app, service)
```

</TabItem>
<TabItem value="typescript" label="TypeScript">

Studio is currently available as a Python adapter. You can run it standalone via Docker against any ANIP service:

```bash
docker build -t anip-studio studio/
docker run -p 3000:80 anip-studio
# Open http://localhost:3000 and connect to http://localhost:9100
```

</TabItem>
<TabItem value="go" label="Go">

Studio is currently available as a Python adapter. You can run it standalone via Docker against any ANIP service:

```bash
docker build -t anip-studio studio/
docker run -p 3000:80 anip-studio
# Open http://localhost:3000 and connect to http://localhost:9100
```

</TabItem>
<TabItem value="java" label="Java">

Studio is currently available as a Python adapter. You can run it standalone via Docker against any ANIP service:

```bash
docker build -t anip-studio studio/
docker run -p 3000:80 anip-studio
# Open http://localhost:3000 and connect to http://localhost:9100
```

</TabItem>
<TabItem value="csharp" label="C#">

Studio is currently available as a Python adapter. You can run it standalone via Docker against any ANIP service:

```bash
docker build -t anip-studio studio/
docker run -p 3000:80 anip-studio
# Open http://localhost:3000 and connect to http://localhost:9100
```

</TabItem>
</Tabs>

Open Studio to browse discovery, manifest, JWKS, audit, checkpoints, and invoke capabilities through a UI.

## What to notice

- **Discovery** tells the agent what the service offers before any authentication
- **The manifest** is signed — the agent can cryptographically verify the service's claims
- **Tokens** are scoped — the agent gets exactly the authority it needs, nothing more
- **Permissions** are checkable before invoke — no more "try and see what happens"
- **Failures** include structured recovery guidance, not just error codes
- **Audit** is automatic and queryable — every action is recorded

## Next steps

- **[Install](/docs/getting-started/install)** — Full package lists for all runtimes
- **[Capability Declaration](/docs/protocol/capabilities)** — Deep dive into how capabilities work
- **[Studio & Showcases](/docs/getting-started/studio-showcases)** — Run the full showcase apps
