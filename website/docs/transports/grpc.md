---
title: gRPC
description: gRPC gives ANIP a stronger fit for typed internal service environments.
---

# gRPC

The gRPC binding is for environments that already prefer typed internal RPC.

## Why gRPC exists

gRPC is not the default ANIP path.

It matters when the surrounding platform already uses:

- protobuf schemas
- service mesh
- mTLS
- internal control-plane services

## Current position

The ANIP gRPC binding is defined through a shared proto contract and currently implemented first in Python and Go.

## What it signals

gRPC support matters less as a developer convenience and more as evidence that ANIP can operate inside serious internal platform environments, not only as an HTTP tool layer.
