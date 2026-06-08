# GTM Python Native Bundle

This bundle is the Python-native GTM implementation for language parity.

It is intentionally different from `gtm_pipeline_python`: the older bundle
preserves handwritten Python ANIP services as a reference implementation. This
bundle keeps generated ANIP capability declarations and fills only implementation
seams such as `backend_adapter.py`, `policy.py`, and app-level approval routes.

The parity rule is:

- Generated `capabilities.py` and `runtime_target.py` remain contract truth.
- Custom implementation code may execute GTM behavior behind those generated
  declarations.
- The handwritten reference Python services are not used as ANIP service
  endpoints in language-parity runs.

For now, this bundle reuses helper modules from `gtm_pipeline_python` as
implementation libraries. It does not import or mount the handwritten service
apps from that bundle.
