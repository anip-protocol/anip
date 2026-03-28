---
title: Conformance and Contract Testing
description: ANIP ships tooling for both protocol correctness and behavioral truthfulness.
---

# Conformance and Contract Testing

ANIP has two different validation layers.

## Conformance

Conformance asks:

> Does this implementation speak ANIP correctly?

It validates wire-level and protocol-level behavior across implementations.

## Contract testing

Contract testing asks:

> Does this service behave as it declares?

It validates claims such as:

- read purity
- classification consistency
- cost presence
- compensation workflow behavior

## Why both matter

A service can pass conformance while still being misleading about behavior.

ANIP treats those as separate concerns on purpose:

- protocol correctness
- behavioral truthfulness
