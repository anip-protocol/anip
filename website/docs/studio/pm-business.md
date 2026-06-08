---
title: Studio for PM and Business Users
description: How product and business users use Studio to define governed agent behavior before developers generate ANIP services.
---

# Studio for PM and Business Users

Studio gives product and business owners a way to define what an agent-facing service should do before developers turn it into generated code.

The PM/business role is not to write endpoint schemas. The role is to define governed execution behavior:

- What should the agent be allowed to ask for?
- What should the service do when information is missing?
- What must require approval?
- What must be denied?
- What can be restricted or partially answered?
- What evidence should be recorded?
- What risks should be visible before publication?

## Product Design Is The Business Baseline

Product Design is the business-facing baseline for the project. It should capture:

| Section | What it should answer |
| --- | --- |
| Goals | What business outcome should this ANIP service support? |
| Actors | Who can use it, and what roles or scopes matter? |
| Scenarios | What real requests should the service handle? |
| Non-goals | What should be explicitly out of scope? |
| Risks | What can go wrong if the agent acts incorrectly? |
| Approvals | Which actions need review before execution? |
| Denials | Which requests must stop before backend action? |
| Restrictions | Which data or actions may be partially available? |
| Audit expectations | What evidence must be retained? |

This baseline should be understandable without reading generated JSON.

## What PM Owns

PM/business users should own:

- Scenario intent.
- User and actor definitions.
- Business scope.
- Approval policy intent.
- Denial/restriction rules.
- Risk acceptance.
- Release approval for the selected lineage.

They should not need to own:

- Runtime package layout.
- Backend SDK code.
- Generated service files.
- Transport-specific implementation details.
- Registry signing internals.

## Scenario-Driven Design In Studio

Studio should help Product Design start from scenarios, not endpoints.

Weak starting point:

```text
Expose create_issue, transition_issue, search, comment.
```

Better Product Design starting point:

```text
When a support lead asks to create a Sev-2 customer-impacting bug,
the service should prepare a Jira issue preview, require required fields,
deny unsupported projects, and stop for approval before mutation.
```

The first version is a tool list. The second version is a governed execution scenario.

## What Good Product Design Looks Like

A strong Product Design baseline has:

- Clear business language.
- Explicit actors and permissions.
- Concrete happy paths.
- Missing-input scenarios.
- Ambiguous-input scenarios.
- Approval scenarios.
- Denial scenarios.
- Restricted-output scenarios.
- Follow-up scenarios after clarification or approval.
- Audit expectations.
- Non-goals.

If the Product Design only contains happy paths, the generated ANIP service is likely to behave poorly under real agent use.

## Product Baseline Lock

The Product Design baseline should be locked before release-grade Developer Design proceeds.

Locking the baseline means:

- Product intent has been reviewed.
- The team agrees this is the business behavior to implement.
- Developer Design can be checked for coverage against this baseline.
- Later changes should create a new revision instead of silently changing release intent.

Locking is not bureaucracy. It is how Studio prevents product intent from being lost during technical implementation.

## Diagnostics PM Should Care About

PM/business users should pay attention to diagnostics that say:

- Product Design items are not covered by Developer Design.
- Approval expectations are missing.
- Optional inputs affect business scope but lack omission behavior.
- Capabilities look like raw backend operations instead of governed business actions.
- Denial or restricted paths are not represented.
- Release lineage is not approved.

Those are product risks, not just developer warnings.

## Release Approval

Before package publication, Studio should make the selected release lineage visible:

```text
Product Design revision -> Developer Definition revision -> Package version
```

PM approval should apply to that lineage. If the developer definition changes after approval, the approval should not silently apply to the new lineage.

## What PM Should Review Before Publish

Before approving publication, review:

- Product Design baseline.
- Developer coverage summary.
- Capability list in business language.
- Approval/denial/restriction behavior.
- Readiness findings.
- Package README.
- Public source/project links.
- Absence of secrets or internal-only source docs.
- Release lineage.

The question is not “does the JSON compile?” The question is “does this package represent the behavior we are willing to publish?”

For the design methodology behind these reviews, see [Scenario-Driven Execution Design](/docs/concepts/scenario-driven-execution).
