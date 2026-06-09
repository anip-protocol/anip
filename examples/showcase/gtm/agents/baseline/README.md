# Baseline Agent

This is the first agent runtime for the GTM showcase.

It is intentionally thin:

- it parses a small bounded set of GTM question families
- it issues purpose-bound tokens to the GTM pipeline service
- it invokes ANIP capabilities over HTTP
- it serves a very small UI for the hero demo path

The point is not to show a magical planner. The point is to show that a simple
runtime can consume the same governed GTM service correctly.
