# ANIP Reference Implementation — Flight Booking Service

A working demonstration of the Agent-Native Interface Protocol.

## Setup

```bash
cd examples/anip
pip install -e .
```

## Run

Start the server:

```bash
uvicorn anip_server.main:app --reload
```

Run the demo (in a separate terminal):

```bash
python demo.py
```

## What the Demo Shows

The demo script acts as an AI agent interacting with an ANIP-compliant flight booking service. It walks through the full protocol:

1. **Profile handshake** — agent checks service compatibility before interacting
2. **Delegation chain** — human delegates to orchestrator, orchestrator delegates to booking agent (DAG structure)
3. **Permission discovery** — agent queries what it can do before trying anything
4. **Capability graph** — agent discovers prerequisites (must search before booking)
5. **Capability invocation** — search flights (read), then book (irreversible)
6. **Failure scenarios** — insufficient scope, budget exceeded, purpose mismatch — each with actionable resolution

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/anip/manifest` | GET | Full ANIP manifest with all capability declarations |
| `/anip/handshake` | POST | Profile compatibility check |
| `/anip/tokens/register` | POST | Register a delegation token |
| `/anip/permissions` | POST | Permission discovery given a delegation token |
| `/anip/invoke/{capability}` | POST | Invoke a capability with delegation chain |
| `/anip/capabilities/{name}/graph` | GET | Capability prerequisite graph |
