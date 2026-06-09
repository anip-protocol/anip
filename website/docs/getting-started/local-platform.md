---
title: Run the Local Platform
description: Start Registry and Studio locally with clean databases and seeded showcase data.
---

# Run the Local Platform

Use this path when you want to evaluate ANIP as a platform: Registry, Studio, packages, templates, and generated showcases.

This walkthrough intentionally starts with browse-only local behavior. External credentials for Jira, Slack, GitHub, GitLab, Linear, Notion, or Superset live in local env files and are only needed for live smoke tests.

## Prerequisites

- Docker.
- Docker Compose.
- Git.
- The ANIP repository checked out locally.

No cloud credentials are required for the local browse path.

## 1. Start Registry

From the repo root:

```bash
cd registry
docker compose up --build
```

Open:

```text
http://127.0.0.1:8200/registry/packages
```

The local Registry includes:

- Package browse pages under `/registry/packages`.
- Template browse pages under `/registry/templates`.
- API routes under `/registry-api/v1`.
- Postgres dependency managed by compose.

Reset Registry when you want a clean publication database:

```bash
docker compose down -v --remove-orphans
```

Run Registry smoke:

```bash
registry/scripts/smoke-compose.sh
```

## 2. Start Studio

In another terminal:

```bash
cd studio
docker compose up --build
```

Open:

```text
http://127.0.0.1:8080
```

Studio uses Postgres through compose and seeds showcase projects by default when `STUDIO_SEED_SHOWCASES=1`.

The seeded projects are examples, not hidden state. They should be inspectable through the same pages a user would use for their own work:

- Source Docs.
- Product Design.
- Developer Design.
- Developer Definition.
- Registry Publication.
- Template export/import surfaces.

## 3. Run read-only demo mode

```bash
STUDIO_READ_ONLY=1 STUDIO_SEED_SHOWCASES=1 docker compose up --build
```

Use this mode for hosted public demos. It lets users browse but not mutate:

- No project creation.
- No document edits.
- No assistant runs.
- No package publication.
- No template publication.
- No Registry mutation from Studio.

## 4. Verify both stacks

Registry:

```bash
registry/scripts/smoke-compose.sh
```

Studio:

```bash
studio/scripts/smoke-compose.sh
```

These smoke scripts are release gates. If either fails, fix the stack before trusting local demo behavior.

## 5. Optional live credentials

Keep live integration credentials outside the repository. The showcase smokes use local env files such as:

```text
/tmp/anip-jira.env
/tmp/anip-slack.env
/tmp/anip-github.env
/tmp/anip-gitlab.env
/tmp/anip-linear.env
/tmp/anip-notion.env
```

Those files should contain secret refs or tokens for local testing only. They must never be committed.

## 6. What to try next

- Browse the GTM project in Studio.
- Browse fronting projects in Studio.
- Open Registry packages.
- Generate code from a package.
- Verify a package with `anip verify`.
- Run a GTM language compose stack.

The local platform should make ANIP understandable without requiring external accounts.
