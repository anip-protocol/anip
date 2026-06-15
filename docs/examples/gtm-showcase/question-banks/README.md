# GTM Question Banks

This folder contains the broad question inventory for the GTM showcase.

The purpose is to show that the showcase is not anchored to a tiny canned prompt
set. Each live phase now has a `50`-question bank covering:

- happy paths
- clarification paths
- denials
- restrictions
- approvals
- actor-aware variation
- wording variation
- compound scenario composition where applicable

Files:

- [phase1-question-bank.md](./phase1-question-bank.md)
- [phase2-question-bank.md](./phase2-question-bank.md)
- [phase3-question-bank.md](./phase3-question-bank.md)
- [phase4-question-bank.md](./phase4-question-bank.md)
- [phase5-question-bank.md](./phase5-question-bank.md)
- [phase6-question-bank.md](./phase6-question-bank.md)
- [phase7-question-bank.md](./phase7-question-bank.md)

Each phase also has a matching `.json` file with the same content in structured
form.

The official `gtm-pipeline-q2-review@0.4.4` release gate combines:

- `350` main phase questions from this folder;
- `140` wording-variation questions from `../variation-question-banks-v3/`;
- `24` hard-mode governance cases from `../hard-mode-governance-scenarios.md` and `../../../../benchmarks/gtm-agent-comparison/cases/gtm-hard-mode.json`.

The benchmark suite also expands multi-turn coverage. It converts the `5`
existing clarification-follow-up entries from the main bank into explicit
two-turn cases, then adds `50` generated two-turn clarification/resolution
cases. The resulting `540`-case benchmark suite is used for token, loop,
latency, and model-tier comparisons. It is intentionally separate from the
official broad release gate so release validation and benchmark analysis stay
easy to reason about.

These banks are also executed against the live GTM stack:

- broad execution results: [question-bank-runs/README.md](../question-bank-runs/README.md)
