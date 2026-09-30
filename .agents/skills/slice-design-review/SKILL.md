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
to turn the inspected facts and discovery results into a concrete proposal.
Follow [Interface Design Review](../../../docs/development/slice-workflow.md#interface-design-review)
for required content, presentation guidance, and approval to omit review items.
Use pseudocode when it clarifies consequential changes.
For instruction-only work, show the proposed wording and resulting records.

Fill the format's question table using
[Handling Unanswered Questions](../../../docs/development/slice-workflow.md#handling-unanswered-questions).

## Discuss and Record

Present the concrete proposal in chat and incorporate maintainer feedback.
Use the [interview protocol](../../../docs/development/interview-protocol.md#synthesize-and-resume)
to synthesize the discussion. For material revisions, follow
[Requirements and Approval](../../../docs/development/slice-workflow.md#requirements-and-approval)
and prepare the [revision format](../../../docs/development/templates/slice-records.md#material-revision).

After acceptance, complete the design format's acceptance fields. Follow the
publication paths in
[Interface Design Review](../../../docs/development/slice-workflow.md#interface-design-review).
Use [github-workflow](../github-workflow/SKILL.md#publish-specifications-and-decisions)
to publish and verify the complete design and acceptance record before implementation.
On resumption, compare new findings with that record; apply the same review
section's rules for material changes and
[Advancing Through Phases](../../../docs/development/slice-workflow.md#advancing-through-phases)
for routine choices within the accepted design.
