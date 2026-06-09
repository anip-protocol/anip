# GTM Go Parity Proxy Bundle

This bundle overlays the generated Go backend adapter and entrypoint so the generated ANIP host can delegate GTM business behavior to the reviewed Python GTM services.

The bundle is implementation material, not signed contract truth. Use it for language parity checks where the generated Go substrate should preserve ANIP behavior while provider-specific GTM logic remains in the reviewed Python implementation.

Required environment:

- `GTM_ACTOR_TOKENS_JSON`: actor id to downstream bearer token map
- `GTM_BACKEND_SERVICES_JSON`: service id to downstream base URL map
- `ANIP_API_KEYS_JSON`: inbound API key to principal map
- `ANIP_SERVICE_FILTER`: generated service id hosted by this process

The generated host must keep its public declarations identical to the signed
contract. Proxy behavior belongs in the backend adapter; declaration mutation
environment hooks are intentionally not supported.
