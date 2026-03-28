---
title: stdio
description: stdio gives ANIP a native local-agent transport without opening a network port.
---

# stdio

The stdio binding carries ANIP over JSON-RPC 2.0 on stdin/stdout.

## When it is useful

stdio is especially useful when:

- an agent spawns a local subprocess
- no network port is desirable
- the workflow is local and tightly scoped

## What it proves

stdio is important because it shows ANIP is not tied to HTTP.

The same protocol semantics still apply:

- discovery
- tokens
- permissions
- invoke
- audit
- checkpoints

That gives ANIP a local-agent story that does not require an HTTP server.
