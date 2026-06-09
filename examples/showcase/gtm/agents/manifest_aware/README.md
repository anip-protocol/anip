# Manifest-Aware Agent

This runtime consumes the same GTM pipeline ANIP service as the baseline agent,
but it first reads the service discovery and manifest documents and uses that
metadata to choose the bounded capability surface.

The point is not "smarter prompting." The point is to show that a different
agent implementation can still stay inside the same governed ANIP contract.
