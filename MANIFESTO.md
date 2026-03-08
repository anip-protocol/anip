# The ANIP Manifesto

Every major interface paradigm emerged when the dominant consumer of software changed.

Command-line interfaces emerged for humans at terminals. Graphical interfaces emerged for humans with mice and screens. APIs emerged for programs written by humans. Each shift wasn't cosmetic — it was a fundamental rethinking of how software presents itself, based on who is using it.

That shift is happening again. The dominant consumer of digital services is becoming an AI agent — not a human, and not a deterministic program authored by a human. A reasoning, planning, adapting entity that needs to discover what's possible, understand what's dangerous, and act with appropriate authority.

**We are not building for this.**

Instead, we are building workarounds. Computer-use agents — where LLMs operate a mouse and keyboard against interfaces designed for human eyes and hands — are extraordinary feats of engineering. They are also an admission of failure. They exist because we haven't built the thing that should exist: interfaces designed natively for machines.

Teaching an AI to click buttons on a screen is the equivalent of teaching a human to communicate by manipulating individual pixels. It works. It's impressive. It is not the answer.

REST APIs get closer but still miss. They were designed with a specific assumption: a human developer reads documentation, writes deterministic code against known endpoints, and ships something that always does the same thing. The consumer was always a human-authored program. MCP and similar protocols add a discovery layer, but they're still REST with a wrapper. The agent is still guessing, still discovering permissions by getting rejected, still learning costs by being charged.

The problem is not that our interfaces are bad. The problem is that they are built for the wrong consumer.

**We believe:**

Software interfaces for AI agents should be designed from the ground up for AI agents — not adapted, not wrapped, not bolted onto human-centric interfaces as an afterthought.

Agents should know what a service can do before calling it. They should know what it costs, what it changes, and whether it can be undone. They should carry verifiable authority, not opaque tokens. They should fail with actionable context, not status codes designed for browser error pages.

Every assumption that today's interfaces leave implicit — identity, permissions, side effects, cost, observability — should be explicit, typed, and queryable.

**Machines should talk to machines using machine interfaces, not human interfaces.**

This is what Agent-Native Interface Protocol is for. Not a patch on REST. Not a wrapper around existing APIs. A new interface paradigm for a new kind of consumer.

We're early. The spec is incomplete. The hard problems — trust, verification, multi-agent coordination — are ahead of us. We'd rather define this thoughtfully and in the open than let it emerge ad-hoc behind closed doors.

If this resonates, [read the spec](SPEC.md). If you disagree, [open an issue](https://github.com/anip-protocol/anip/issues). Either way, the shift is happening. The question is whether we design for it or keep building workarounds.
