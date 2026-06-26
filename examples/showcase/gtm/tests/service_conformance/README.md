# GTM Service Conformance

This gate tests generated ANIP service behavior without an LLM planner.

It verifies:

- The same package produces equivalent generated services across Python, TypeScript, Go, Java, and C#.
- Canonical capability invocations return the expected ANIP outcomes.
- Approval, denial, clarification, restriction, masking, and success behavior are service-owned.
- Requested effects are passed through the runtime context where supported.

This gate does not test natural-language routing. Natural-language routing is covered by the deterministic routing gate and the LLM benchmark gate.

Run against a started generated service:

```bash
python examples/showcase/gtm/tests/service_conformance/run_service_conformance.py \
  --base-url http://127.0.0.1:4100 \
  --cases examples/showcase/gtm/tests/service_conformance/cases.json
```

Each case names the service URL, capability, parameters, actor, token scope, requested effects, and expected ANIP outcome. The runner does not call OpenAI or the GTM agent UI.
