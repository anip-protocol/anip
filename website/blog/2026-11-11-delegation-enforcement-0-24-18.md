---
slug: delegation-enforcement-0-24-18
title: "ANIP 0.24.18: Our Runtimes Did Not Enforce Our Own Delegation Rules"
authors: [anip]
tags: [release, security, delegation, conformance]
---

ANIP 0.24.18 is a security release. If you run an ANIP service with more than one principal or more than one capability, upgrade.

The short version: the specification has always said how delegation must be restricted. Our five runtimes did not all enforce it. Three of them enforced much less than the other two, and none of them enforced all of it.

<!-- truncate -->

The full list is in advisory [GHSA-h9rv-5v5h-pmr6](https://github.com/anip-protocol/anip/security/advisories/GHSA-h9rv-5v5h-pmr6) and in the [release notes](/docs/releases/delegation-enforcement-0-24-18). This post explains what went wrong and why we missed it.

## What was wrong

ANIP's delegation model rests on a few rules. A token works for one capability. A delegated token can only narrow what its parent allows. Only the holder of a token can delegate from it. Chains have a depth limit.

Here is what each runtime actually did before 0.24.18:

| Rule | Python | TypeScript | Go | Java | C# |
|---|---|---|---|---|---|
| A token works only for the capability it was issued for | enforced | enforced | missing | missing | missing |
| A delegated token cannot widen its parent's scope | enforced | enforced | missing | missing | missing |
| Only the holder of a token can delegate from it | bypassable on stdio and gRPC | bypassable | missing | missing | missing |
| Delegation chains deeper than the limit are rejected | enforced | enforced | missing | missing | missing |
| A token cannot be used to obtain a root token | missing | missing | missing on stdio and gRPC | enforced | enforced |
| A scope budget cannot be shed when delegating | partly | partly | missing | missing | missing |

Two of these are worth stating plainly.

On Go, Java and C#, a caller with any valid credential could ask for a token delegated from someone else's token, knowing only its ID. The new token acted under that other principal and could read their audit entries.

On TypeScript, and on Python's stdio and gRPC transports, a caller that presented a narrow token on the token endpoint was treated as the human at the root of that token's chain. It could get a root token in that human's name, with any scope.

For a protocol whose purpose is to bound what an agent may do, these are not edge cases. They are the core promise.

## Why we missed it

Three things lined up.

**The conformance suite did not test these rules.** It checked the shape of responses, lineage, budgets and recovery guidance. It never tried to use a token for the wrong capability, widen a scope, or delegate from a token it did not hold. All five runtimes passed, and passing meant less than we thought.

**Some tests asserted the wrong behaviour.** Eight tests across Go, Java and C# either expected the gap or passed for an unrelated reason. One was named "child cannot widen parent" and contained a comment noting that the widened child token gets issued.

**The runtimes were ported, not specified twice.** Python and TypeScript were written first and carried most of the checks. The later ports reproduced the happy path, and nothing forced them to reproduce the refusals.

Our own [security policy](https://github.com/anip-protocol/anip/blob/main/SECURITY.md) describes side-effect declarations as "declared, not verified". The same turned out to be true of our claim that every runtime enforces delegation. It was declared in the specification and not verified by anything.

## How it was found

Not by an outside report. We were checking whether a set of fixes made in the Python runtime had left the other languages behind. Composed capabilities behaved differently between runtimes, and tracing why led to the missing token check in Go. From there we stopped reading code and started probing running services, one rule at a time.

That review was done with an AI coding assistant. It wrote the probes and the tests, found most of the gaps, and made the fixes, with a person deciding at each step what to do with the findings, including the decision to fix this privately before publishing.

## What changed

- **All five runtimes enforce the same rules.** The delegation checks are implemented in each runtime and behave the same way.
- **The conformance suite now tests them.** `conformance/test_delegation.py` has 15 checks that try each forbidden thing against a running service and require a refusal.
- **Composed capabilities run each step on its own token.** A step's token is delegated from the caller's, bound to the step's capability, and never holds more than the caller's token.
- **CI runs every language on a schedule.** Tests used to run only when a language's files changed, which hid breakage for months.

## What you need to do

Upgrade to 0.24.18. Three behaviour changes may affect you:

- Issue one token per capability. A token only invokes the capability it names.
- To delegate, authenticate with the token you hold and name it as `parent_token`. Root tokens need the bootstrap credential.
- If a scope carries a budget, keep a budget on anything delegated beneath it.

The [release notes](/docs/releases/delegation-enforcement-0-24-18) cover each change and how to run the new conformance checks against your own service.

## What we take from this

A protocol is only as trustworthy as the checks that can be run against an implementation of it. We had a specification, five runtimes and a conformance suite, and still shipped three runtimes that let one principal act as another.

The fix for that is not more careful porting. It is conformance tests that attempt the forbidden thing and fail the build when it works. That is what 0.24.18 adds for delegation, and it is how we intend to treat the remaining rules that are currently only declared.
