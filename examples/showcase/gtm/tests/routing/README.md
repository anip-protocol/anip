# GTM Deterministic Routing

This gate tests natural-language-to-capability routing without invoking a model.

The router may use:

- Package capability ids.
- Declared inputs.
- Declared produced and forbidden effects.
- Composition metadata.
- App-specific aliases generated from reviewed package evidence.

The router must not use benchmark-specific exact-question branches. If a request is ambiguous, the expected result is clarification, not a guessed capability.

Run against a generated agent profile:

```bash
PYTHONPATH=packages/python/anip-runtime-utils/src \
python examples/showcase/gtm/tests/routing/run_routing_conformance.py \
  --profile /path/to/agent-consumption/agent-app-profile.json \
  --cases examples/showcase/gtm/tests/routing/cases.json
```

This gate is not a replacement for LLM benchmarks. It proves the package carries enough deterministic routing evidence before a model is allowed to fill parameters or explain results.
