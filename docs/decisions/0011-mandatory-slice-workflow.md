# Decision-0011: Mandatory Slice Workflow

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-09-18</date>
<owners>Gurubodh maintainers</owners>

## Current Applicability

This decision remains accepted. The restructuring under
[#357](https://github.com/Team-Gurubodh/gurubodh/issues/357) makes the
[slice workflow](../development/slice-workflow.md) the sole maintained lifecycle
policy and routes supporting skills and guides to it. The text below records
adoption and rationale; consult that workflow for current operational rules.

## Context

[Decision-0008](./0008-slice-development-pilot.md) limited the slice workflow to
a pilot tracked in [#289](https://github.com/Team-Gurubodh/gurubodh/issues/289).
The pilot and retrospective are recorded there, including the
[migrated handoff archive](https://github.com/Team-Gurubodh/gurubodh/issues/289#issuecomment-5571636976).
During [#355](https://github.com/Team-Gurubodh/gurubodh/issues/355), the maintainer
explicitly directed that the workflow become mandatory for all GitHub issue
work until they decide otherwise, and authorized the coordinated policy updates.

## Decision

Adopt the [slice workflow](../development/slice-workflow.md) repository-wide,
effective 2026-09-18. This supersedes Decision-0008's pilot-only applicability.
The workflow remains mandatory until the maintainer changes or withdraws it.
Design review and explicit maintainer acceptance are mandatory before
implementation; that phase cannot be bypassed. Individual review items require
approval to become optional. Other phases may be brief or marked not applicable
with a reason. Record scoped maintainer exceptions in the relevant issue while
preserving these design-review protections.

Root [AGENTS.md](../../AGENTS.md) requires agents to read and follow the workflow
before planning or implementation. The GitHub workflow skill and contributor
guides route to that same contract. Requirement coverage, phase outcomes,
verification, reconciliation, and issue-comment session handoffs apply to all
issue work.

Record session handoffs in the parent issue, or in the slice's sub-issue with
links to parent coverage, from the first session using the workflow. After
promotion, sub-issues own detailed execution records; the parent retains a
summary, requirement coverage, statuses, and links. Slice-completion records
are separate from session handoffs unless both events coincide.

Track implementation verified, published for review, and delivered separately.
Issue completion and closure require the maintainer's explicit confirmation
of "implementation verified" and instruction to complete and close the issue.
Successful checks or PR publication do not supply that authorization.

## Rationale

One explicit workflow makes issue execution predictable for contributors and
agents. Root instruction routing makes the requirement discoverable, and phase
outcomes allow effort to scale with the task. Issue comments keep scope,
execution evidence, and handoffs together without competing task histories.

## Impact

The workflow, agent instructions, skill, contributor guides, and documentation
indexes describe the adopted policy. Reviewers check coverage and evidence
before accepting completion claims. These are instruction and review controls;
this decision does not add automated enforcement or redesign issue templates.

Existing issue-first, branch, verification, and explicit merge-authorization
rules continue to apply. Adoption does not authorize integration, close #289,
or require migration or deletion of existing task records.

## Review Trigger

Record evidence and proposed refinements in a relevant GitHub issue. Change or
withdraw the policy only with an explicit maintainer decision, and update the
workflow and its entry points together.
