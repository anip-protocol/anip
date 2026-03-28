---
title: Showcase Apps
description: Three full ANIP services demonstrating real-world patterns across travel, finance, and DevOps.
---

# Showcase Apps

ANIP includes three showcase applications that demonstrate the full protocol surface in realistic domains. These are not toy examples — they exercise delegation, side-effect declarations, cost signaling, structured failures, audit, and all four interface surfaces.

## Available showcases

| Showcase | Domain | Capabilities | Key patterns |
|----------|--------|-------------|--------------|
| **Travel** | Flight booking | search_flights, check_availability, book_flight, cancel_booking | Read vs. irreversible, cost signaling, compensation workflow |
| **Finance** | Portfolio management | query_portfolio, get_market_data, execute_trade, transfer_funds, generate_report | Financial cost, budget-bound delegation, high-risk audit classification |
| **DevOps** | Infrastructure | list_deployments, get_service_health, scale_replicas, update_config, rollback_deployment, delete_resource | Transactional with rollback, irreversible deletion, operational side effects |

## Running a showcase

Each showcase mounts all four HTTP surfaces — native ANIP, REST, GraphQL, MCP — plus Studio:

```bash
cd examples/showcase/travel
pip install -e ".[dev]"
python app.py
# → ANIP:    http://localhost:9100/anip/*
# → REST:    http://localhost:9100/api/*
# → GraphQL: http://localhost:9100/graphql
# → MCP:     http://localhost:9100/mcp
# → Studio:  http://localhost:9100/studio/
```

## What to explore

1. **Discovery** — `curl http://localhost:9100/.well-known/anip` to see the full service shape
2. **Studio** — Open `http://localhost:9100/studio/` to browse capabilities, check permissions, and invoke
3. **Side effects** — Compare `search_flights` (read) with `book_flight` (irreversible) in the manifest
4. **Failures** — Try invoking `book_flight` with insufficient budget to see structured failure with resolution guidance
5. **Audit** — Query the audit log to see invocations logged with event classification
