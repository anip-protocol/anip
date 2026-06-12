---
title: Generate a Service
description: Generate ANIP service code from a definition, package bundle, Registry package, or fronting starter.
---

# Generate a Service

Use `anip generate` when you already have a reviewed ANIP artifact and want runnable service code.

Generation can start from:

- A local service definition.
- A downloaded package bundle.
- A trusted Registry package.
- A fronting starter that produces an ANIP definition before a signed package exists.

The important rule: generated code is not the source of truth. The service definition or signed package is the behavior contract. Custom code may fill implementation seams, but it must not rewrite the public capability surface.

## 1. Generate From A Local Definition

Use this path when you have an `anip-service-definition.json` locally:

```bash
anip generate \
  --definition ./anip-service-definition.json \
  --target python \
  --transport http,stdio \
  --dependency-source local \
  --output ./generated/my-service \
  --force
```

This is useful for local development, CI fixtures, and generated service smoke tests.

## 2. Generate From A Package Bundle

Use this path when you have a downloaded `.anip-package.json` bundle:

```bash
anip generate \
  --package-bundle ./my-service-0.2.0.anip-package.json \
  --target typescript \
  --transport http,stdio \
  --dependency-source local \
  --output ./generated/my-service \
  --force
```

This gives the generator the immutable package metadata, service definition, lineage, signature material, and optional implementation metadata.

## 3. Generate From Registry

Use this path when consuming a trusted Registry package:

```bash
anip generate \
  --registry-url https://registry.anip.dev/registry-api/v1 \
  --package-id gtm-pipeline-q2-review \
  --package-version 0.4.3 \
  --target go \
  --transport http \
  --dependency-source registry \
  --output ./generated/gtm-pipeline \
  --force
```

For production use, also write and commit a lock:

```bash
anip generate \
  --registry-url https://registry.anip.dev/registry-api/v1 \
  --package-id gtm-pipeline-q2-review \
  --package-version 0.4.3 \
  --target go \
  --write-lock ./anip-package-lock.json \
  --output ./generated/gtm-pipeline \
  --force
```

The lock records the package identity and digest expected by the consumer.

## 4. Choose Language And Transport

Supported targets:

```text
python
typescript
go
java
csharp
```

Supported generated transports:

```text
http
stdio
http,stdio
```

Use HTTP for deployed services and Docker Compose stacks. Use stdio for local agent clients that expect a process-style service without network setup.

## 5. Add Custom Code

Most real services need implementation material:

- Backend adapters.
- Database access.
- Approval stores.
- Domain rendering.
- Provider-specific validation.
- Framework wiring.

Attach that material with a custom bundle:

```bash
anip generate \
  --package-bundle ./my-service-0.2.0.anip-package.json \
  --target python \
  --custom-code-bundle ./custom-code-bundles/my-service-python \
  --output ./generated/my-service \
  --force
```

Valid custom bundle behavior:

- Implement declared capabilities.
- Connect to backend systems.
- Resolve provider data behind `resolver_ref`.
- Return previews or approval-required responses according to the contract.
- Adapt generated service code to language or framework conventions.

Invalid custom bundle behavior:

- Add hidden capabilities.
- Remove required inputs.
- Change side-effect posture.
- Weaken approval policy.
- Rewrite input-resolution behavior.
- Mutate the public manifest away from the signed package.

## 6. Fronting Example: Jira

Fronting is one generation path. It creates a governed ANIP service in front of an existing system.

Fronting is not a tool rename exercise:

```text
Jira API exposes operations.
ANIP exposes allowed Jira behaviors.
```

Before a signed package exists, you can scaffold from a reviewed starter:

```bash
cd packages/go
go run ./cmd/anip fronting scaffold \
  --starter ../../docs/examples/jira-fronting-showcase/anip-fronting-starter.json \
  --target python \
  --dependency-source local \
  --transport http,stdio \
  --output /tmp/anip-jira-fronting \
  --force
```

The output includes:

```text
/tmp/anip-jira-fronting/
  anip-service-definition.json
  integration-fronting/
  src/
  tests/
```

Once the project is reviewed and packaged, generate from the signed package instead:

```bash
go run ./cmd/anip generate \
  --package-bundle ../../examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3.anip-package.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/jira_fronting/custom-code-bundles/jira_fronting_python \
  --transport http,stdio \
  --output /tmp/anip-jira-fronting-from-package \
  --force
```

The generated service exposes governed capabilities such as:

```text
jira.backlog.search_context
jira.issue.get_context
jira.incident_bug.prepare
jira.workflow_transition.request
jira.release_notes.prepare
```

It does not expose raw Jira methods as the agent-facing product surface. Jira REST is the execution binding. ANIP owns clarification, approval, denial, restriction, and audit semantics.

## 7. Validate And Test

Validate the generated definition:

```bash
anip validate --definition ./generated/my-service/anip-service-definition.json
```

Run generated tests:

```bash
cd ./generated/my-service
pytest tests
```

For live smokes, keep credentials outside the repo:

```bash
cat >/tmp/anip-jira.env <<'EOF'
JIRA_BASE_URL=https://your-site.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=...
JIRA_PROJECT_KEY=SCRUM
EOF
```

Mutation smokes should require an explicit local flag:

```bash
ANIP_JIRA_ALLOW_MUTATION=true
```

That flag is only a test harness guard. Write-adjacent capabilities should still return `approval_required` unless a valid ANIP approval grant is provided.

## Next Steps

- Use [Start With Registry](/docs/getting-started/registry) to find packages and templates.
- Use [Package Trust Loop](/docs/getting-started/package-trust-loop) to verify and lock packages.
- Use [Fronting](/docs/patterns/fronting) for the full fronting architecture.
- Use [Custom Code Bundles](/docs/generated-services/custom-code-bundles) to understand implementation seams.
