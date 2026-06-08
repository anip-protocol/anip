---
title: Fronting Validation Levels
description: How ANIP fronting showcases separate contract proof, generated-service proof, adapter proof, and live backend proof.
---

# Fronting Validation Levels

Fronting showcases should not use one vague word like "works". A governed fronting package has several independent proof points.

| Level | What it proves | What it does not prove |
| --- | --- | --- |
| Contract-ready | Studio produced reviewed Product Design, Developer Design, Developer Definition, and a service definition with governed capabilities, backend mappings, policies, outcomes, and audit shape. | No generated code or backend adapter has been exercised yet. |
| Package-ready | Registry package verifies and can be consumed as the behavior authority. | It does not prove a specific language runtime or credentialed backend path. |
| Generated-service ready | CLI generation and generated tests pass for a target language and runtime package version. | It does not prove real backend calls unless a custom adapter is present. |
| Adapter-ready | A reviewed custom bundle fills the backend seam without changing the signed contract. | It may still be unit-tested or mocked only. |
| Live-read ready | The adapter has been exercised against real credentials for bounded reads, searches, metadata, or preview preparation. | It does not prove writes or approval continuation. |
| Approved-mutation ready | A real approval grant plus an explicit test flag prove that the service stops before approval and mutates only after approval. | It should be limited to a disposable test workspace, repo, project, channel, page, or database. |
| Five-language live-adapter parity | Python, TypeScript, Go, Java, and C# generate from the same package, include equivalent custom adapters, and pass matching live smokes. | It does not mean every production deployment should enable every mutation. |

This distinction is important because the signed ANIP package and the backend adapter are intentionally separate. The package is the governed behavior contract. The adapter is the provider-specific execution binding.

## Release Checklist

Before a fronting package is presented publicly as release-quality:

- The Studio project should be reproducible from source docs or a reviewed template.
- Product Design should lock before Developer Design work starts.
- Developer Definition should save with no blockers and no readiness warnings.
- Registry package verification should pass.
- Generated services should pass in all supported target languages.
- Custom bundles should exist for the claimed live-adapter languages.
- Live smokes should use dedicated test credentials and explicit mutation flags.
- Approved mutation tests should prove both denial-before-approval and success-after-approval.

If a showcase has not passed one of these levels, the docs should say exactly which level it has passed.

