# GTM C# Native Bundle

Custom implementation material for the generated C# GTM language-parity service.

This bundle intentionally keeps GTM-specific behavior outside the generic ANIP generator:

- DB-backed pipeline, forecast, bottleneck, team, product, stalled opportunity, risk, and enrichment summaries.
- Fixture-backed prioritization and outreach examples.
- Preview-only approval records for follow-up preparation, reassignment, routing, and derived-target outreach.

The generated ANIP substrate remains contract-driven. This bundle fills only the backend adapter seam and additive GTM approval endpoints.

