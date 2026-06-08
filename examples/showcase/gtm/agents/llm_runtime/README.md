# LLM Runtime

This runtime uses one configurable OpenAI-compatible chat model to plan exactly
one bounded ANIP invocation against services supplied through configuration.

The reusable substrate is domain-agnostic. Domain/product behavior belongs in an
optional app profile module, such as `gtm_agent_app.py`, loaded with
`ANIP_AGENT_APP_MODULE=gtm_agent_app`.

ANIP is not intended to make every possible business agent zero-glue. The
runtime should remove service-integration glue: discovery, scopes, token
issuance, invocation, approval boundaries, standard failures, and verified
package metadata. Product/app glue is still valid when it is explicit and kept
outside the reusable substrate.

It does not receive the full ANIP spec. It receives:

- a generic ANIP planning prompt
- a compact capability brief derived by `anip-runtime-utils` from live ANIP discovery and manifest data

The runtime still keeps full capability metadata locally for deterministic
normalization, token issuance, invocation, and audit. The model sees the compact
routing brief, not raw manifest/package JSON on every call.

Required environment:

- `ANIP_AGENT_MODEL` or `OPENAI_MODEL`
- `ANIP_AGENT_API_KEY` or `OPENAI_API_KEY`
- `ANIP_AGENT_SERVICES_JSON`

Optional environment:

- `ANIP_AGENT_BASE_URL` or `OPENAI_BASE_URL`
- `ANIP_AGENT_TEMPERATURE`
- `ANIP_AGENT_TIMEOUT_SECONDS`
- `ANIP_AGENT_ACTORS_JSON`
- `ANIP_AGENT_DEFAULT_ACTOR_ID`
- `ANIP_AGENT_DEFAULT_BEARER_TOKEN`
- `ANIP_AGENT_APP_MODULE`
- `ANIP_AGENT_ALLOW_DUPLICATE_SERVICE_URLS`

`ANIP_AGENT_SERVICES_JSON` should normally contain unique service URLs. Duplicate
URLs are rejected by default because they duplicate catalog discovery and can
make the last service alias win for capability metadata. Set
`ANIP_AGENT_ALLOW_DUPLICATE_SERVICE_URLS=true` only for an intentional aggregate
service experiment, not for language-parity runs.

The substrate is deliberately domain-agnostic. It does not contain hardcoded
capability routing, domain regex normalization, pre-call helpers, workflow
special cases, or benchmark stop logic. Domain service URLs and demo actor
tokens belong in deployment configuration. Product-specific prompt/framing and
temporary app-level metadata belong in the app profile.

Allowed app-profile glue includes:

- product framing and tone
- compact `business_effects` or boundary hints when not yet contract-published
- input meaning hints for product enum values
- reference catalogs for demo or app-visible selections
- selection hints for product UX preference between otherwise valid capabilities
- result display guidance

Not allowed in the reusable substrate:

- GTM capability IDs or service names
- benchmark-specific question handling
- phrase lists that simulate product policy
- hidden multi-service workflows
- service-specific authorization or approval shortcuts

Services may also provide generic approval proxy paths in `ANIP_AGENT_SERVICES_JSON`:

- `approval_list_path`
- `approval_approve_path_template` with `{approval_request_id}`

The governed service remains the source of truth for:

- clarification
- denial
- approval stops
- bounded evidence

The GTM app profile is therefore part of the example application, not proof
that arbitrary agents need no app layer. The honest claim is that ANIP makes
that app layer smaller, inspectable, and separated from service-integration
mechanics.
