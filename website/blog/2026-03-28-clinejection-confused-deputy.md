---
slug: clinejection-confused-deputy
title: "The Clinejection Attack: Why Agent Interfaces Need Purpose-Bound Authority"
authors: [anip]
tags: [security, delegation, trust]
---

4,000 developer machines. One GitHub issue title. Eight hours.

That's the Clinejection attack from last month. If you haven't read it, here's the chain: an attacker crafted a GitHub issue title containing an embedded instruction. An AI triage bot read it, interpreted it as legitimate, and executed `npm install` from a typosquatted repository. That triggered a cache poisoning attack that exfiltrated npm credentials. Six days later, 4,000 developers installed a compromised Cline release that silently bootstrapped a second AI agent on their machines — with shell access, credential access, and a persistent daemon surviving reboots.

Five steps. The entry point was natural language.

<!-- truncate -->

## The root cause wasn't the prompt injection

The post-mortems focused on the prompt injection. Fix the sanitization, remove the AI triage workflow, adopt OIDC provenance. All correct. None of them address the root cause.

The root cause was that the AI triage bot had no machine-readable contract for what it was authorized to do. It had a token and shell access. That was the entire authorization model.

The bot was deployed to triage issues. Nothing in the interface enforced that boundary. When the injected instruction said "run npm install from this repository," the bot had no mechanism to evaluate whether that action was within its authorization — because the authorization was never expressed in a form the interface could check. The token was valid. The shell was accessible. The operation executed.

## The confused deputy at production scale

This is the confused deputy problem at production scale. The developer trusted Cline. Cline (via compromise) delegated that trust to OpenClaw. The developer never authorized OpenClaw. Nothing in the interface captured that distinction.

We are deploying agents against systems that have no concept of purpose-bound authority. The agent carries a token. The token is valid or it isn't. Everything else is implicit — inferred from documentation nobody read, constrained by policy nobody enforced, logged in audit trails that captured what happened but not why the agent believed it was authorized to act.

## What changes with purpose-bound delegation

Under an interface designed for agents rather than humans, this attack looks different.

The triage bot's delegation token declares a purpose: issue triage. Its scope covers triage operations — reading issues, writing labels, posting comments. Not `ci.install`. Not irreversible filesystem modifications.

When the injected instruction triggers an `npm install`, the interface checks the delegation chain:

```json
{
  "scope": ["issues.read", "issues.label", "issues.comment"],
  "capability": "triage_issue",
  "purpose_parameters": { "task": "issue-triage" }
}
```

Purpose mismatch. The requested operation (`ci.install`) is not in the granted scope. Operation rejected.

Not because the model caught the injection — because the interface enforced the authorization boundary before execution.

The prompt injection is still a problem. The model still processed untrusted input. But the blast radius collapses from "exfiltrated credentials and 4,000 compromised machines" to "a rejected operation and an audit log entry."

## The permission discovery difference

Under ANIP, the triage bot could also have checked its permissions before attempting any action:

```json
{
  "available": [
    { "capability": "read_issue", "scope_match": "issues.read" },
    { "capability": "add_label", "scope_match": "issues.label" }
  ],
  "restricted": [
    { "capability": "install_package", "reason": "missing scope: ci.install", "grantable_by": "human:admin@org.com" }
  ],
  "denied": [
    { "capability": "shell_execute", "reason": "requires admin principal class" }
  ]
}
```

The agent knows — before acting — that `install_package` and `shell_execute` are not available to it. Even if the injected instruction triggers an attempt, the interface rejects it and logs the attempt.

## This isn't hypothetical

Every team deploying AI agents in CI/CD right now — for issue triage, code review, automated testing — has this exact exposure. The agent processes untrusted input and has access to secrets. The question is whether anything evaluates what the agent does with that access before it acts.

The patch fixes the symptom. The interface design is the disease.

## What ANIP provides

[ANIP](/) is an open protocol that makes these boundaries part of the interface:

- **Purpose-bound delegation**: Tokens carry scope, capability, and purpose constraints — not just "valid / invalid"
- **Side-effect typing**: The interface distinguishes read from write from irreversible — the agent knows what kind of change it's making
- **Permission discovery**: The agent can check what it's allowed to do before attempting anything
- **Structured failures**: When an operation is rejected, the response tells the agent why and who can authorize it
- **Audit with lineage**: Every action is logged with the full delegation chain — who authorized it, under what scope, for what purpose

The world is not going to stop deploying agents. The question is whether we give them interfaces that can express and enforce authorization — or keep handing them tokens and hoping for the best.

---

*ANIP is open source: [github.com/anip-protocol/anip](https://github.com/anip-protocol/anip)*
