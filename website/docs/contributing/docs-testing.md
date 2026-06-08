---
title: Documentation Testing
description: Keep documentation examples aligned with the shipped CLI, packages, and compose stacks.
---

# Documentation Testing

Documentation is part of the product. ANIP docs should not contain commands that only worked on one developer machine.

## What must be tested

Test these docs surfaces before release:

- Website production build.
- CLI help examples.
- Registry local compose.
- Studio local compose.
- Read-only Studio mode.
- Package verification examples.
- Fronting generation examples.
- GTM language parity compose examples.
- Any command that publishes, verifies, generates, or runs a service.

## Required local checks

From the website directory:

```bash
npm run build
```

From the repository root:

```bash
registry/scripts/smoke-compose.sh
studio/scripts/smoke-compose.sh
```

Check CLI help:

```bash
anip --help
anip generate --help
anip verify --help
anip fronting scaffold --help
anip package build-local --help
anip package attach-implementation --help
```

## Snippet rules

Docs snippets should be:

- Copy-pasteable.
- Version-aware.
- Free of secrets.
- Free of local machine paths unless explicitly marked as local examples.
- Prefer `anip` over compatibility wrappers unless documenting wrapper compatibility.
- Use `http://127.0.0.1` for local browser/API examples.
- Use `/tmp/...` for throwaway output.
- Use explicit package IDs and versions for showcase examples.

## Commands that should not be blindly tested

Some commands are intentionally illustrative:

- Commands that publish to a real Registry.
- Commands that mutate Jira, Slack, GitHub, GitLab, Linear, Notion, or Superset.
- Commands requiring user-owned API tokens.
- Commands that create external infrastructure.

For these, docs should show:

- Required env vars.
- Read-only smoke path.
- Mutation guard flag.
- Approval requirement.
- Secret handling guidance.

## Browser review

After the build passes, review key pages in a browser:

- [Introduction](/docs/intro)
- [First 10 Minutes](/docs/getting-started/first-10-minutes)
- [ANIP Studio](/docs/tooling/studio)
- [ANIP Registry](/docs/tooling/registry)
- [Governed Fronting](/docs/patterns/fronting)
- [Protocol Reference](/docs/protocol/reference)
- [Troubleshooting](/docs/operations/troubleshooting)

Check:

- Sidebar order.
- Code block wrapping.
- Copy buttons.
- Tables on narrow screens.
- Mermaid diagrams.
- Link routing.
- No stale terminology.

## Release gate

Do not treat documentation as done until:

- `npm run build` passes.
- New pages are reachable from the sidebar.
- Commands match CLI help.
- Examples point to real files.
- Public docs avoid secrets and machine-local links.
- New concepts are linked from at least one onboarding page and one reference page.

Bad documentation creates support load and damages trust. Keep docs tested with the same discipline as generated code.
