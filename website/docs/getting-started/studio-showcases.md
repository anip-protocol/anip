---
title: Studio and Showcases
description: The fastest way to see ANIP in action — run a showcase app and open Studio.
---

# Studio and Showcases

If you're evaluating ANIP, this is the fastest path to understanding what it does. Run a showcase app and open Studio to explore the full protocol surface visually.

## Quick start

```bash
# Clone the repo
git clone https://github.com/anip-protocol/anip.git
cd anip

# Install the travel showcase and its dependencies
cd examples/showcase/travel
pip install -e ".[dev]"

# Run it
python app.py
```

Now open [http://localhost:9100/studio/](http://localhost:9100/studio/) in your browser.

## What to explore in Studio

1. **Discovery** — see the full service shape: capabilities, trust posture, endpoints
2. **Manifest** — expand each capability to see side-effect declarations, cost hints, required scopes, input/output contracts
3. **Invoke** — select a capability, enter `demo-human-key` as the bearer token, fill in inputs, and invoke. See success results or structured failures with resolution guidance
4. **Audit** — browse the audit log to see every invocation recorded with event classification

## Try these scenarios

### See permission discovery in action
1. Go to the Invoke view → select `book_flight`
2. Enter `demo-human-key` → permissions panel shows what's available vs. restricted
3. Try invoking — see the structured failure if scope or budget is insufficient

### Compare side-effect types
- `search_flights` is `read` — safe to call speculatively
- `book_flight` is `irreversible` — the manifest warns the agent this is permanent

### See structured failures
- Invoke `book_flight` with a budget below the flight cost
- The failure response includes `failure.type`, `failure.detail`, `failure.resolution.action`, and `failure.resolution.grantable_by`

## All three showcases

| Showcase | Command | Key patterns |
|----------|---------|--------------|
| Travel | `cd examples/showcase/travel && python app.py` | Cost signaling, irreversibility, compensation |
| Finance | `cd examples/showcase/finance && python app.py` | Financial operations, budget delegation |
| DevOps | `cd examples/showcase/devops && python app.py` | Transactional rollback, infrastructure changes |

Each runs at `http://localhost:9100` with Studio at `/studio/`.
