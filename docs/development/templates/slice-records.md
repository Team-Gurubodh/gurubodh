# Slice Record Formats

Copy the applicable format into the issue that owns the record; replace
placeholders and remove instructional hints. These are aids to the
[slice workflow](../slice-workflow.md), which defines required content.
Link existing contracts and records instead of maintaining competing copies.

## Parent Coverage and Slice Plan

Use one parent checklist under [requirement coverage](../slice-workflow.md#requirement-coverage).

```markdown
## Requirement coverage

| ID | Requirement or constraint | Slice | Status | Evidence / remaining work |
| --- | --- | --- | --- | --- |
| R1 | ... | S1 | pending / in progress / partial / satisfied | ... |

## S1 — <outcome>

- Outcome and exclusions:
- Covered requirements and acceptance criteria:
- Boundaries/contracts and design record:
- Accepted scope, optional review items, and open questions:
- Verification plan, including real integration boundaries:
- Current phase and phase outcome:
- Execution status and completion evidence:
- Verification / publication / delivery status and required destination:
- Remaining parent requirements and next action:
```

When promoting a slice to a sub-issue, use the
[ownership split](../slice-workflow.md#lightweight-slice-checklist): keep the
parent's summary, coverage, status, obligations, and links; move detailed
execution records to the sub-issue.

## Design and Acceptance

Use for proposals and accepted designs under
[interface design review](../slice-workflow.md#interface-design-review).
Do not label a proposal accepted until the maintainer has accepted it.

```markdown
## S1 — Design <version>; <proposed / accepted>

- Parent coverage link and requirements:
- Outcome, exclusions, acceptance criteria:

| Module/path | Abstractions, responsibilities, and changes from current behavior |
| --- | --- |
| ... | ... |

- Functions/interfaces: before/after signatures, types, errors, side effects;
  state explicitly when none change.
- Collaboration: callers/dependencies, data crossing boundaries, ownership.
- Contract: inputs/outputs, validation, compatibility, success/failure examples.
- Rationale: assumptions, alternatives, tradeoffs, recommendation.
- Verification: independent expectations, fixtures, commands, integration checks.

| Question | Blocking/nonblocking and reason | Affected work/dependencies | Resolution or due point |
| --- | --- | --- | --- |
| ... | ... | ... | ... |

### Acceptance record

- Maintainer confirmation and source (link or exact chat instruction):
- Accepted version/scope and revisions:
- Optional review items explicitly approved, or none:
- Unresolved questions and permitted independent work, or none:
- Phase outcome and next action:
```

## Slice Completion

Use after [integration and reconciliation](../slice-workflow.md#slice-reconciliation).
This records slice execution, not issue closure.

```markdown
## S1 — Slice execution complete

- Accepted design and coverage links:
- Changes and acceptance-criteria results:
- Verification: commands/scenarios, results, verifier, evidence:
- Skipped checks: exact checks, reasons, remaining uncertainty, decisions:
- Requirement reconciliation: satisfied, partial, outstanding, newly found gaps:
- Phase outcome and execution status:
- Work location: branch, commits, PR; local/committed/published:
- Implementation verified: by whom and evidence; maintainer confirmation status:
- Published for review: evidence or pending:
- Delivered: destination, evidence or pending:
- Remaining parent obligations, dependencies, and next action:
```

## Session Handoff

Use at [session exit](../slice-workflow.md#session-entry-and-exit), including
pauses within a phase. If session exit coincides with slice completion, combine
the records and include both sets of information.

```markdown
## Session handoff

This session is ending <at the stopping point / for transfer>.

- Active slice and phase; phase and slice complete or in progress:
- Coverage, accepted design, decisions, and earlier evidence links:
- Completed work:
- Verification results and exact skips/reasons:
- Unresolved questions and affected work:
- Outstanding parent requirements:
- Branch/commit/PR and whether changes are local, committed, or published:
- Implementation verification (agent and maintainer), publication, delivery:
- Pending design acceptance, completion/closure decisions, or delivery actions:
- Next action:
```
