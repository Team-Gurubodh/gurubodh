---
name: slice-design-review
description: Investigate Gurubodh implementation, discover consequential design choices, and prepare concrete slice plan/design reviews and acceptance records. Use for an initial design or material changes to an accepted design.
---

# Slice Design Review

The [interface design review](../../../docs/development/slice-workflow.md#interface-design-review)
defines the required review areas, acceptance gate, and question handling.
This skill helps produce the review; it does not add approval requirements.

## Investigate and Discover Design Choices

Read the active slice's scope, mapped requirements, existing acceptance record,
and relevant implementation/contracts. Trace real callers and boundaries before
proposing modules or interfaces. For documentation, inspect authority, reading
routes, incoming links, retained instructions, and retirement destinations.

Before finalizing the proposal, read the shared
[interview protocol](../../../docs/development/interview-protocol.md). Account
for these topics using inspected facts, settled decisions, and informed choices;
explain any topic's inapplicability:

| Topic | What to establish |
| --- | --- |
| Compatibility | Behavior/interfaces to preserve and permitted breaking changes. |
| Abstractions, ownership, responsibilities | Existing or proposed abstractions and who owns each responsibility. |
| Interfaces and collaboration | Signatures, exchanged data, dependencies, and interactions. |
| Failure semantics | Errors, partial results, retries, and recovery ownership. |
| Persistence | State that survives interruption and its lifecycle. |
| Operational behavior | Invocation, configuration, observability, recovery, and maintenance. |
| Tradeoffs | Meaningful alternatives, consequences, and the recommendation. |

Ask about unresolved choices affecting behavior, contracts, or maintainer
preferences. Resolve routine implementation details through existing conventions
and the accepted design. If investigation exposes a product question, return it
to [slice-session](../slice-session/SKILL.md) and pause dependent design until the
affected requirement is settled and any revision accepted. Preserve unrelated
accepted decisions.

## Prepare a Concrete Proposal

Use the [design format](../../../docs/development/templates/slice-records.md#design-and-acceptance)
to distinguish current behavior, proposed changes, and undecided choices.
Show file paths and responsibilities; sketch changed signatures and errors;
trace data and ownership between collaborators. Include representative success
and failure cases and explain compatibility and side effects. If no functions
or runtime abstractions change, say so explicitly. Existing abstractions may
suffice; do not invent them to fill a table.

Identify the active slice's plan and design versions, mapped requirements, and
verification approach. Walk through concrete behavior examples, module tables,
changed signatures, failure/boundary cases, alternatives, and verification. Use
diagrams or pseudocode when they clarify interactions or consequential logic.
For instruction-only changes, show proposed instruction excerpts and resulting
records. Each format must help assess the work; all required review areas still
apply.

Explain assumptions, alternatives, and the recommendation. Classify questions
by their effect on the accepted contract and verification, identify dependencies,
and describe the independent work, if any, that can proceed under existing
acceptance. Use the workflow's rules for optional review items.

## Discuss and Record

Present the concrete proposal in chat and incorporate maintainer feedback.
Discuss affected changes, then present one complete identified version for
acceptance. For each material revision, link the superseded decisions and name
affected requirements and dependencies. Follow the workflow's
acceptance gate before implementation; general implementation authorization
is not a substitute for a design decision.

Record the accepted plan/design subjects, versions and scope, maintainer
confirmation, revisions, optional-item approvals, and remaining questions in
the execution issue. Link existing specifications and parent coverage. Use
[github-workflow](../github-workflow/SKILL.md) to post and verify the record.

On resumption, reuse that record. If new findings materially change interfaces,
responsibilities, or collaboration, identify affected work and return it to the
workflow's design discussion before proceeding. Resolve other routine choices
within the accepted boundary without reopening acceptance.
