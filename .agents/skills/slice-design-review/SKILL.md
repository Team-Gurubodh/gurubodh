---
name: slice-design-review
description: Prepare concrete Gurubodh slice design reviews and record accepted scope, review-item decisions, and blocking questions. Use for an initial design or material changes to an accepted design.
---

# Slice Design Review

The [interface design review](../../../docs/development/slice-workflow.md#interface-design-review)
defines the required review areas, acceptance gate, and question handling.
This skill helps produce the review; it does not add approval requirements.

## Prepare a Concrete Proposal

Read the active slice's scope, mapped requirements, existing acceptance record,
and relevant implementation/contracts. Trace real callers and boundaries before
proposing modules or interfaces. For documentation, inspect authority, reading
routes, incoming links, retained instructions, and retirement destinations.

Use the [design format](../../../docs/development/templates/slice-records.md#design-and-acceptance)
to distinguish current behavior, proposed changes, and undecided choices.
Show file paths and responsibilities; sketch changed signatures and errors;
trace data and ownership between collaborators. Include representative success
and failure cases and explain compatibility and side effects. If no functions
or runtime abstractions change, say so explicitly. Existing abstractions may
suffice; do not invent them to fill a table.

Explain assumptions, alternatives, and the recommendation. Classify questions
by their effect on the accepted contract and verification, identify dependencies,
and describe the independent work, if any, that can proceed under existing
acceptance. Use the workflow's rules for optional review items.

## Discuss and Record

Present the concrete proposal in chat and incorporate maintainer feedback.
For each revision, make the changed boundary clear. Follow the workflow's
acceptance gate before implementation; general implementation authorization
is not a substitute for a design decision.

Record the accepted version and scope, the maintainer's confirmation, revisions,
optional-item approvals, and remaining questions in the execution issue. Link
existing specifications and parent coverage. Use
[github-workflow](../github-workflow/SKILL.md) to post and verify the record.

On resumption, reuse that record. If new findings materially change interfaces,
responsibilities, or collaboration, identify affected work and return it to the
workflow's design discussion before proceeding. Resolve other routine choices
within the accepted boundary without reopening acceptance.
