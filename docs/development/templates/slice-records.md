# Slice Record Formats

Copy the applicable format into the issue that owns the record; replace
placeholders and remove instructional hints. These are aids to the
[slice workflow](../slice-workflow.md), which defines required content.
Link existing contracts and records instead of maintaining competing copies.

## Requirements Specification

Use for new or materially revised scope under
[requirements and approval](../slice-workflow.md#requirements-and-approval).
Keep one current requirements/coverage record in the parent. Link established
answers, distinguish facts/decisions/recommendations/assumptions, and explain
inapplicable discovery dimensions. A proposal is a draft until explicitly accepted.

```markdown
## Specification <version> — <draft / accepted>

- Users and problem:
- Journey: trigger, actions, expected sequence:
- Facts and explicit maintainer decisions: evidence/source links:

| ID | Requirement: actor, trigger, behavior, observable result | Acceptance criteria/examples |
| --- | --- | --- |
| R1 | ... | Success, failure, boundary cases |

- Inputs/outputs and sources:
- Failure behavior: invalid input, dependency failure, interruption, partial success:
- Constraints: compatibility, performance, operations, privacy, cost:
- Included work, exclusions, and proposed deferrals:
- Inapplicable dimensions and reasons, or none:
- Recommendations/assumptions and classified questions: use the question table below:
- Acceptance: confirmation/source, subject/version/scope; pending if draft:
- Coverage: link the existing parent checklist:
```

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
- Specification and plan/design versions, boundaries/contracts, record links:
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
Publish one complete identified design before implementation. Link accepted
requirements and unchanged contracts; explain changes in the proposal.
Do not label a proposal accepted until the maintainer has accepted it.

~~~markdown
## S1 — Plan <version> and design <version>; <proposed / accepted>

- Accepted specification and parent coverage links; mapped requirement IDs:
- Proposed active-slice outcome, exclusions, and acceptance criteria; or link
  an existing accepted plan and identify proposed changes, if any:

| Changed module/path | Abstractions, responsibilities, and change from current behavior |
| --- | --- |
| ... | ... |

- Changed functions/interfaces: before/after contracts, signatures, types,
  errors, side effects. List mechanically identical internal edits and their
  shared transformation once; identify exceptions. State when none change.
- Collaboration: callers/dependencies, data crossing boundaries, ownership.
- Contract: inputs/outputs, validation, compatibility, representative
  success/failure examples.
- Rationale: assumptions, alternatives, tradeoffs, recommendation.
- Verification plan: independent expectations, fixtures, commands,
  integration checks; link detailed results when available.

| Question and context (fact/decision/recommendation/assumption) | Blocking/nonblocking and reason | Affected work/dependencies | Proposed optional default | Resolution or due point |
| --- | --- | --- | --- | --- |
| ... | ... | ... | ... | ... |
~~~

After explicit acceptance, record all fields below in either publication path.
If the complete, current proposal is already published, use a compact acceptance
comment linking it. Otherwise publish the complete accepted design and append
these acceptance fields or link a separate acceptance record. An accepted label
alone does not establish confirmation or scope. Material contract changes follow
[material revision](#material-revision), including version identification and
explicit acceptance. A consolidated replacement identifies the record it
supersedes and preserves acceptance history.

~~~markdown
## S1 — Plan <version> and design <version> accepted

- Complete design location (this comment or link); accepted subjects, versions, and scope:
- Maintainer confirmation and source:
- Exact clarifications/changed sections; material revision version and
  superseded record link, or none:
- Approved optional review items, or none:
- Unresolved questions, affected work, and permitted independent work, or none:
- Publication readback status, interface-design phase outcome, and next action:
~~~

The question table also applies to specifications. For a nonblocking question,
state why current work is independent of the answer. An optional default remains
an agent recommendation until decided. A combined plan/design acceptance names
both subjects and versions; specification acceptance is separate. When acceptance
is pending, leave the confirmation pending instead of inserting example approval.

## Material Revision

Use when changing accepted requirements or design. Preserve unrelated accepted
decisions and earlier confirmations. Link the affected content; do not create a
second current requirements checklist.

```markdown
## <Specification / slice plan/design> <new version> — <draft / accepted>

- Changed requirement IDs/decisions and proposed replacement:
- Reason and supporting evidence:
- Supersedes: affected record/version link; unchanged decisions remain valid:
- Affected work/dependencies; work paused and independent accepted work permitted:
- Classified questions, or none:
- Acceptance needed/received: subjects, versions, scope, confirmation/source:
- Publication: saved and verified / unsaved / unverified; evidence or recovery action:
```

## Slice Completion

Use after [integration and reconciliation](../slice-workflow.md#slice-reconciliation).
This records slice execution, not issue closure. Link detailed evidence already
recorded, including earlier in the same session, and its exact skips. Include
details here only where no durable record contains them; a separate verification
comment is not required. Keep current outcomes and milestones explicit.

~~~markdown
## S1 — Slice execution complete

- Accepted design and current coverage links:
- Acceptance-criteria results and changes:
- Verification: concise outcome and durable evidence link; where not already
  recorded, commands/scenarios, observed results, verifier, exact skips,
  reasons, remaining uncertainty, and decisions:
- Requirement reconciliation: satisfied, partial, outstanding, new gaps:
- Phase and slice outcome; remaining parent obligations:
- Work location: branch, commit, PR; local/committed/published:
- Milestones: implementation verifier and maintainer confirmation state;
  publication and delivery destination/evidence or pending:
- Next action:
~~~

## Session Handoff

Use at [session exit](../slice-workflow.md#session-entry-and-exit), including
pauses within a phase. If session exit coincides with slice completion, combine
the records and include both sets of required information. Repeat the minimum
current-state fields even when unchanged. Link detailed records already posted,
including earlier in the same session; state when earlier facts are unchanged
without copying their narratives. Include full evidence details here only where
no durable record contains them; no separate verification comment is required.
Keep the status and next action explicit in the handoff itself.

~~~markdown
## Session handoff — <slice>

This session is ending <at the stopping point / for transfer>.

- Current state: slice/phase and completion state; outstanding requirement
  IDs, blockers, and open questions/affected work; current coverage and design links:
- Work location: branch/commit/PR; local, committed, or published state:
- Milestones and gates: agent and maintainer implementation verification, publication, delivery;
  recorded acceptance or draft/unsaved/unverified state with subject,
  version, source/recovery action when relevant; pending maintainer decisions:
- This session: completed work, new decisions, concise verification outcomes,
  changed questions; link detailed records, including those from this session.
  Where evidence is not already recorded, include commands/scenarios, observed
  results, verifier, exact skips/reasons, uncertainty, and related decisions:
- Unchanged earlier decisions/evidence/skips/questions: link current record,
  or state none applies:
- Next action:
~~~
