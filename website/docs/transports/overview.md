---
title: Transport Overview
description: ANIP semantics stay the same across HTTP, stdio, and gRPC.
---

# Transport Overview

ANIP is transport-agnostic.

The protocol surface stays the same even when the carrier changes.

Current bindings:

- HTTP
- stdio
- gRPC

## Why this matters

It lets ANIP fit different environments:

- HTTP for default service integration
- stdio for local agent subprocess workflows
- gRPC for internal platform and service-mesh environments

ANIP is the protocol layer. The transport is how it is carried.
