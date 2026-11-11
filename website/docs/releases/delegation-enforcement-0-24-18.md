---
title: "0.24.18: Delegation Enforcement"
description: Security release. All five runtimes now enforce the same delegation rules. What changed and how to upgrade.
---

# 0.24.18: Delegation Enforcement

This is a security release. The protocol version stays `anip/0.24`; what changes is that every runtime now enforces delegation rules the specification already required. Advisory: [GHSA-h9rv-5v5h-pmr6](https://github.com/anip-protocol/anip/security/advisories/GHSA-h9rv-5v5h-pmr6).

Upgrade if your service has more than one principal or more than one capability.

## What was wrong

| Rule | Python | TypeScript | Go | Java | C# |
|---|---|---|---|---|---|
| A token works only for the capability it was issued for | enforced | enforced | **missing** | **missing** | **missing** |
| A delegated token cannot widen its parent's scope | enforced | enforced | **missing** | **missing** | **missing** |
| Only the holder of a token can delegate from it | **bypassable** on stdio and gRPC | **bypassable** | **missing** | **missing** | **missing** |
| Delegation chains deeper than the limit are rejected | enforced | enforced | **missing** | **missing** | **missing** |
| A token cannot be used to obtain a root token | **missing** | **missing** | missing on stdio and gRPC | enforced | enforced |
| A scope budget cannot be shed when delegating | **partly** | **partly** | **missing** | **missing** | **missing** |

Two cases deserve a plain description:

- On Go, Java and C#, a caller with any valid credential could ask for a token delegated from another principal's token by giving its token ID. The new token acted under that principal and could read that principal's audit entries.
- On TypeScript, and on Python's stdio and gRPC transports, a caller that presented a narrow token on the token endpoint was treated as the human at the root of that token's chain. It could obtain a root token in that human's name with any scope, and could delegate from that human's tokens. This is what "bypassable" means in the table.

## What changes for you

These are behaviour changes. Most integrations that follow the documented flow are unaffected; the first one is the most likely to be noticed on Go, Java and C#.

- **Issue one token per capability.** A token invokes only the capability named in its `capability` field. A token issued without a capability can no longer invoke anything. Reusing one token across capabilities fails with `purpose_mismatch`.
- **Delegate with the token you hold.** To delegate, authenticate with your own token (or the bootstrap credential, if you are the token's subject) and name it as `parent_token`. Go, Java and C# now accept a token as the credential on the token endpoint for this purpose; before, they only accepted the bootstrap credential.
- **Root tokens need the bootstrap credential.** Presenting a token and omitting `parent_token` fails with `insufficient_authority`.
- **Keep scope budgets when delegating.** If the parent scope is `travel:max_$500`, a child scope such as `travel.book` must carry a budget of at most 500.
- **Python and TypeScript: `authenticate_bearer` / `authenticateBearer` is bootstrap-only.** It no longer resolves a delegation token to a principal. Use `resolve_bearer_token` / `resolveBearerToken` to invoke with a token. Transports that build their own token endpoint should call `authenticate_issuer` / `authenticateIssuer` and `issue_token_as` / `issueTokenAs`.

## Composed capabilities

Composed capabilities relied on the missing checks in Go, Java and C#: child steps ran on the caller's token. In every runtime, each child step now runs with its own token, delegated from the caller's token, bound to the child capability, and narrowed to the child's minimum scope while keeping the caller's scope budget.

- A caller whose token does not cover a child's scope gets `scope_insufficient` for that step, and the child does not run.
- Each child step has its own audit entry, linked to the parent invocation and sharing its `task_id`. Go previously linked child entries to the wrong invocation.
- **Python:** the SDK now runs composed capabilities itself, as the other runtimes already did. The handler registered for a composed capability is no longer called.
- **Generated Python projects** no longer carry their own composition code. Regenerate projects created with an earlier generator; the old generated code called child handlers directly, which skipped each child's token check and audit entry.

## New API surface

| Runtime | Added |
|---|---|
| Python | `ANIPService.authenticate_issuer()`, `ANIPService.issue_token_as()`, `Issuer` |
| TypeScript | `authenticateIssuer()`, `issueTokenAs()`, `Issuer` |
| Go | `Service.AuthenticateIssuer()`, `Service.IssueTokenAs()`, `Issuer`, `server.ValidateDelegation()` |
| Java | `ANIPService.authenticateIssuer()`, `ANIPService.issueTokenAs()`, `Issuer`, `DelegationEngine.validateDelegation()` |
| C# | `AnipService.AuthenticateIssuer()`, `AnipService.IssueTokenAs()`, `Issuer`, `DelegationEngine.ValidateDelegation()` |

## Checking your own service

The conformance suite now includes these rules. Run it against your service:

```bash
pip install -e ./conformance
pytest conformance/test_delegation.py \
  --base-url=http://localhost:9100 \
  --bootstrap-bearer=<your bootstrap credential> \
  --sample-inputs=<your sample inputs file>
```

The tests need a service with at least two capabilities whose scopes do not overlap.
