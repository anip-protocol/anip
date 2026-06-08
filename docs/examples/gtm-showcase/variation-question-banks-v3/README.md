# GTM Variation Question Banks v3

These 140 questions are a regression fixture for agent-consumption behavior on top of ANIP-generated GTM services.

They are intentionally separate from the original 350-question benchmark:

- The 350-pack validates the benchmark contract phases end to end.
- This 140-pack probes language variation and app-consumption semantics, including unsupported effects, derived targets, approval boundaries, enum grounding, and raw-export denial.
- Passing this pack is evidence for the current GTM app profile and shared runtime helpers; it is not a guarantee that a new domain needs no app glue.

Run against a local agent runtime:

```bash
OUT=output/gtm-variation-question-runs
mkdir -p "$OUT"
for phase in 1 2 3 4 5 6 7; do
  python3 examples/showcase/gtm/scripts/generated_stack/run_phase1_regression.py \
    --runtime-url http://127.0.0.1:9304 \
    --cases "docs/examples/gtm-showcase/variation-question-banks-v3/phase${phase}-variation-bank-20.json" \
    --output-dir "$OUT"
done
```

The fixture should remain domain-example data. Generic behavior belongs in shared runtime utilities, Studio-reviewed metadata, or generator-emitted agent-consumption artifacts.
