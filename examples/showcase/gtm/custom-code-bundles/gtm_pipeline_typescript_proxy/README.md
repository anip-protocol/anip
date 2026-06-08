# GTM Pipeline TypeScript Proxy Custom Code Bundle

This bundle is for parity testing the generated TypeScript ANIP host against the
reviewed GTM Python implementation.

It does not change the signed ANIP contract. It fills generated extension seams:

- `src/runtime/backend-adapter.ts` delegates backend execution to the reviewed
  Python GTM service for the capability owner service.
- `src/runtime/policy.ts` lets the downstream reviewed GTM services own
  actor/business policy so the proxy does not double-enforce stale package
  policy before delegation.
- `src/app.ts` keeps the generated ANIP host and adds approval proxy routes used
  by the GTM question-bank harness.

Expected environment:

```bash
ANIP_API_KEYS_JSON='{"demo-sales-leader-key":"human:alex.king@example.com|actor_id=sales_leader|role=sales_leader|pipeline_scope=company|financial_access=full|enrichment_access=full|outreach_access=full|can_prepare_followup=true|can_approve_followup=true|can_use_lookalikes=true|can_route_leads=true|can_approve_routing=true|can_use_objection_variants=true"}'
GTM_ACTOR_TOKENS_JSON='{"sales_leader":"demo-sales-leader-key"}'
GTM_BACKEND_SERVICES_JSON='{"gtm-pipeline-service":"http://127.0.0.1:4100","gtm-enrichment-service":"http://127.0.0.1:4101","gtm-prioritization-service":"http://127.0.0.1:4102","gtm-outreach-service":"http://127.0.0.1:4103"}'
```
