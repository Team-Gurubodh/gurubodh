# Slice Development Workflow

<record_type>workflow_guide</record_type>
<status>active</status>

This is the authoritative issue-execution process delegated by
[AGENTS.md](../../AGENTS.md). Supporting skills explain how to carry out its
activities; they introduce no policy or additional approval gates.

## Reading Route

After reading this workflow, read
[slice-session](../../.agents/skills/slice-session/SKILL.md), restore the issue
context, and select the resources for the active phase below. Agents without
automatic skill discovery must open the linked `SKILL.md` files directly.
Read technical and historical references only when they apply to the work.

| Activity | Skill and references |
| --- | --- |
| Start, resume, or pause | [slice-session](../../.agents/skills/slice-session/SKILL.md); complete issue/discussion, accepted decisions, latest handoff; [session requirements](#session-entry-and-exit) |
| Plan and maintain coverage | slice-session; [coverage](#requirement-coverage), [slice checklist](#lightweight-slice-checklist), applicable goals/contracts |
| Review initial or materially changed design | [slice-design-review](../../.agents/skills/slice-design-review/SKILL.md); [design contract](#interface-design-review), existing implementation and applicable technical references |
| Prepare tests and implement | [phase outcomes](#phase-outcomes), accepted design and questions; component README and relevant contracts/tests |
| Verify and reconcile | [verification](#verification-and-delivery-status), [reconciliation](#slice-reconciliation); component verification commands and real integration boundaries |
| Operate on issues, branches, commits, Projects, or PRs | [github-workflow](../../.agents/skills/github-workflow/SKILL.md), [GitHub conventions](github-workflow.md); optional [command tutorial](git-github-cli-workflow-tutorial.md) |
| Publish, integrate, or close | github-workflow; [publication and integration](#publication-and-integration), [whole-issue completion](#whole-issue-completion) |

Use the [record formats](templates/slice-records.md) when recording coverage,
design acceptance, slice completion, or a handoff. The sections below define
required content; formats are reusable aids, not additional gates.

## Core Terms and Their Relationship

A GitHub issue defines the overall scope. That scope is divided into slices,
each slice is advanced through phases, and sessions are used to carry out the work.

| Term | Definition | When it is complete or ends |
| --- | --- | --- |
| Slice | A bounded unit of an issue's scope with an identified outcome, explicit exclusions, mapped requirements, and acceptance criteria. | Its execution is complete when its acceptance criteria are met, verification evidence is recorded, and its contribution to parent requirements is reconciled in a slice-completion record. Delivery and issue closure are tracked separately. |
| Phase | A named stage of work within a slice, with a required outcome that enables further work on that slice. Examples: Planning, Interface Design. | Complete when its required outcome and any acceptance gate are met. Interface design always requires maintainer acceptance; other phases may be marked not applicable with a recorded reason. New findings may require revisiting a phase. |
| Session | A work period by a contributor or agent that starts with context restoration and a stated intended outcome, and ends with a handoff when work is paused or responsibility transfers. | Ends at the recorded stopping or handoff point, even if the active phase or slice is incomplete. |

A session may span several phases or slices, and a slice may span several
sessions. A chat exchange or phase transition alone does not end a session;
record a handoff when pausing or transferring work. Ending a session does not
establish phase, slice, or issue completion.

## Applicability

This workflow is mandatory for all GitHub issue work in this repository,
effective 2026-09-18 and until the maintainer changes or withdraws the requirement.
Read and apply it before planning or implementation and through verification,
slice reconciliation, whole-issue review, and session handoff. Task size or type
does not exempt the work. Scale phase outcomes to the task, while preserving
the mandatory design-review and maintainer-acceptance gate.

Only an explicit maintainer instruction may grant a scoped workflow exception,
subject to the design-review protections under [Exceptions](#exceptions).
Record the exception in the relevant GitHub issue.

Adoption is recorded in
[Decision-0011](../decisions/0011-mandatory-slice-workflow.md); the earlier pilot
and its history are linked there.

## Authoritative Records

The parent GitHub issue and its discussion own scope, progress, and verification
records. Maintain the [coverage checklist](#requirement-coverage) there.
Project-board status is a view of that progress; see
[Projects tracking](github-workflow.md#projects-tracking).

From the first session using this workflow, record every session handoff as a
comment in the relevant GitHub issue. Use the parent issue unless the slice has
its own sub-issue; in that case, post the handoff in the sub-issue and link to
the parent's authoritative coverage checklist. Keep the parent's coverage and
completion evidence current with links to the relevant sub-issue comments.

Current slice designs, decisions, execution evidence, and handoffs belong in
GitHub issues. When a slice has its own sub-issue, use the ownership split under
[Lightweight Slice Checklist](#lightweight-slice-checklist) rather than keeping
duplicate execution records in the parent and sub-issue.

Keep tentative proposals distinct from accepted decisions. Promote lasting
technical decisions into the appropriate interface, schema, or decision
documentation when implemented. Do not create competing copies of the scope.

## Phase Outcomes

| Phase | Outcome needed to advance |
| --- | --- |
| Planning | Bounded outcome, exclusions, mapped parent requirements, acceptance criteria, and known uncertainties |
| Interface design | Contracts and proposed code structure presented through the [Interface Design Review](#interface-design-review) and explicitly accepted by the maintainer; accepted scope, approved optional items, and classified open questions recorded in the relevant issue before implementation |
| Test preparation | Reviewable success/failure cases, independent expectations, fixtures, and verification commands; executable tests where appropriate |
| Implementation | Small reviewable changes satisfying the agreed contract, with relevant checks passing |
| Integration verification | Evidence using real applicable boundaries, reconciliation against parent requirements, and a slice-completion record; a session handoff only if the session also ends |

### Interface Design Review

Before coding starts, inspect the existing implementation and present the
proposed design in chat for maintainer review and discussion. Show the contract
and the code structure that will realize it, distinguishing existing behavior,
proposed changes, and unresolved questions.

Wait for the maintainer's explicit acceptance of the design before coding or
other implementation begins. Record that acceptance and the design version or
scope it covers in the relevant issue. Presenting a proposal, receiving no
response, or having general authorization to implement does not constitute
design acceptance. This review phase cannot be skipped or marked not applicable.

| Review area | Details to present |
| --- | --- |
| Modules | Names and paths of modules being added or edited, affected abstractions within them, and why the change belongs there. |
| Abstractions and responsibilities | Classes, interfaces, data types, or other relevant abstractions being added or edited; their main responsibilities, ownership, and changes from the existing design. |
| Functions and interfaces | Functions being added or edited, proposed signatures, parameter and return types, relevant errors, and side effects. Show before and after for changed interfaces. |
| Collaboration | Which abstractions call or depend on which others, what data crosses each boundary, and who owns validation, orchestration, persistence, or other relevant responsibilities. |
| Contract and examples | Inputs, outputs, ownership, validation, errors, compatibility, and relevant cross-component behavior, illustrated by typical success and relevant failure cases. |
| Rationale and open decisions | Assumptions, alternatives considered, tradeoffs, the recommendation and its reasons, and questions requiring maintainer judgment. |

Use a module/abstraction table and short signature sketches where useful. Add
a sequence diagram or interaction example when it clarifies collaboration.
Scale the detail to the slice. If a review item seems inapplicable or unnecessary,
explain why and prompt the maintainer for approval to make it optional before
omitting it. Record that approval in the issue. Reporting that no functions
change in a prose-only slice addresses the functions item; it does not omit it.
State when existing abstractions suffice instead of introducing new ones to
fill the review format.

Incorporate the maintainer's feedback from the chat discussion. Before
implementation, record the accepted design and any unresolved questions in a
comment on the parent issue or the slice's execution sub-issue, following
[Authoritative Records](#authoritative-records). Include the applicable review
details above and link existing specifications instead of duplicating them.
Keep proposals distinct from accepted decisions. Classify each open question
as blocking or nonblocking, identify the work and dependencies it affects, and
state what may proceed:

- A blocking question prevents implementation of the affected work and anything
  that depends on its answer. Resolve it and obtain acceptance of the resulting
  design before proceeding with that work.
- A nonblocking question does not affect the accepted contract or verification
  of the work proceeding now. Record why it is nonblocking and when it must be
  resolved; reclassify it if its impact changes.

Independent work within the same slice may proceed only when it is explicitly
covered by the maintainer's accepted design and does not depend on an unresolved
blocking question. The acceptance record must identify that boundary. Future
slices need their own concrete design records; linking this workflow alone is
insufficient.

If implementation reveals a material change to reviewed
interfaces, responsibilities, or collaboration, return to design discussion
and obtain acceptance of the revised design. Update the issue record before
proceeding with that change.

### Advancing Through Phases

Advance when the current phase's outcome is established. Implementation needs
settled acceptance criteria/contracts, the recorded design acceptance above,
and a verification approach, within the user's authorization. Honor dependency
gates recorded in the relevant issues before beginning dependent work.

Ask about unresolved product choices, scope changes, or decisions reserved for
the maintainer. Ordinary technical choices and progress within an accepted
design do not require repeated permission. Other phases may be brief or marked
not applicable with a recorded reason under [Exceptions](#exceptions).

For refactoring, characterize behavior that must survive the change. Use mocks
or fakes to isolate dependencies and exercise failures where helpful. Use real
validators, storage adapters, or other applicable integration boundaries early;
mock agreement alone does not establish integration correctness. Scale checks
to the change and follow the issue's required verification.

## Lightweight Slice Checklist

Record these details for each active slice in the parent issue until the slice
has its own sub-issue:

- Slice ID, outcome, and exclusions.
- Covered requirement references and acceptance criteria.
- Boundaries, accepted contracts, maintainer acceptance, approved optional review
  items, and blocking/nonblocking design questions with affected work.
- Verification plan, including applicable integration checks.
- Current phase and execution/delivery status.
- Completion evidence and remaining parent requirements.

Use this checklist within the existing GitHub issue templates. A separate
template or sub-issue is not required for every slice.

Start with slices in the parent issue. Promote a slice to a sub-issue when it
needs independent ownership, substantial separate discussion, or its own
delivery and dependency tracking. Preserve its slice ID and parent requirement
mapping. Multiple sessions alone do not require a sub-issue. After promotion:

- The parent retains the slice ID, short outcome/exclusions summary, requirement
  mapping, current phase and status, remaining parent obligations, and links to
  the sub-issue and its verification and slice-completion evidence.
- The sub-issue owns the detailed checklist, design and acceptance record,
  questions, verification plan/results, execution discussion, slice-completion
  record, and session handoffs. Link the existing parent discussion when moving
  ownership; do not maintain competing detailed copies.

## Requirement Coverage

Before implementing the first slice, read the full parent issue and available
discussion, including requirements, constraints, and exclusions outside the
acceptance-criteria checkboxes. Assign stable requirement references, slices,
statuses, and evidence in one parent checklist. Assign every requirement to a
slice or explicitly identified subsequent work. No requirement may remain
unassigned. Proposed later slices may be refined; preserve traceability when splitting or regrouping them.

Tracking a requirement in another slice or issue does not remove it from the
parent's completion obligations. It remains outstanding until evidence satisfies
it or the maintainer explicitly approves removing it from the parent's scope.
Record that scope decision in the parent; a follow-up link alone is insufficient.

Use explicit statuses such as pending, in progress, partial, and satisfied.
Mark a requirement satisfied only with implementation/documentation and
verification evidence appropriate to that requirement. Shared requirements
need both incremental evidence and a check across the completed issue.

## Slice Reconciliation

After every slice:

1. Link evidence to the requirements it satisfies.
2. Mark partial satisfaction and remaining work explicitly.
3. Identify uncovered requirements or new gaps and assign them to subsequent
   work; seek maintainer agreement for changes to authoritative scope.
4. Select the next slice from outstanding requirements.

After integration verification and reconciliation, post a slice-completion
comment in the slice's execution issue. Include its ID, acceptance-criteria
results, verification evidence and skips, requirement reconciliation, current
delivery status, remaining parent obligations, and next action. This records
slice execution completion and does not itself end the session or close an issue.

If the session ends at the same point, one comment may serve as both the
slice-completion record and session handoff, provided it includes both sets of
information and explicitly says that the session is ending.

## Verification and Delivery Status

Record these milestones separately for each slice and the issue, with evidence
and any pending milestone made explicit:

| Status | Meaning and evidence |
| --- | --- |
| Implementation verified | The implementation or documentation satisfies its acceptance criteria and required checks, with reconciliation evidence recorded. Changes may still be local and uncommitted. Identify whose verification is recorded; the agent's evidence does not substitute for the maintainer's confirmation required for issue closure. |
| Published for review | The reviewable changes are available to reviewers, normally in a pushed branch and linked PR. Posting a status comment alone does not publish repository changes. |
| Delivered | The result has reached the destination required by the issue, with evidence: for example, merged into the target branch or deployed where the issue requires deployment. Define that destination in the issue; do not infer delivery from verification, PR creation, or issue closure. |

Use the applicable component's documented checks: start with
[repository commands](../../README.md#repository-commands), the
[CMS README](../../apps/gurubodh-cms/README.md),
[content CLI README](../../tools/gurubodh-cli/README.md), or the relevant guide.
Record commands, results, verifier, and evidence. For any skipped check, report
exactly what was skipped, why, and the remaining uncertainty. A skip is not a
pass; resolve required verification gaps or obtain an explicit maintainer
decision before issue completion.

These milestones need not occur in a fixed order: a draft PR may be published
before verification is finished. Always distinguish technical verification,
maintainer confirmation, publication, delivery, and issue closure. None of these
statuses grants permission to merge or deploy.

## Publication and Integration

A slice may be ready for review while other issue requirements remain open.
Prepare a linked PR describing the slice's scope, verification, documentation,
and remaining work using the [PR template](../../.github/PULL_REQUEST_TEMPLATE.md)
and [GitHub conventions](github-workflow.md#pull-requests). A draft PR may expose
unfinished work with its status stated accurately. Report the changes and any
verification skips to the maintainer.

Use `Refs #<issue-number>` until the whole-issue review and maintainer
confirmation/instruction under [Whole-Issue Completion](#whole-issue-completion)
authorize closure. Only then may a closing reference be used.

Merge only after required checks and review pass. Agents need explicit maintainer
instruction before merging, squashing, rebasing, or otherwise integrating into
the target branch. Review approval, design acceptance, verification, publication,
and issue closure do not supply that instruction. After authorized integration,
record delivery evidence and follow [branch cleanup](github-workflow.md#branch-cleanup).

## Whole-Issue Completion

Before requesting that an issue be marked complete, reread its entire description
and discussion. Compare every requirement against implementation, documentation,
and verification evidence, including integration across separately completed
slices. Every requirement must be satisfied with evidence or explicitly
removed from scope by the maintainer. Nothing may be silently deferred.

Passing this review allows the agent to report verification evidence and ask
for the maintainer's completion decision. Mark an issue complete and close it
only after the maintainer explicitly confirms "implementation verified" and
instructs the agent to mark it complete and close it. Record that confirmation
and instruction in the issue. Neither an agent's successful checks, design
acceptance, publication, nor delivery supplies this authorization. This rule
applies to execution sub-issues as well as parent issues.

If the maintainer authorizes closure while publication or delivery is still
pending, record those pending milestones and remaining actions explicitly.
Closure does not mean delivery has occurred and does not authorize a merge.

## Session Entry and Exit

At entry, read the complete authoritative issue and available discussion, accepted
decisions, and latest handoff comment in the relevant issue. Identify the active
slice and phase, and state the intended session outcome. Reuse accepted decisions
instead of reopening them without new evidence.

At exit, post a session handoff comment in the issue selected under
[Authoritative Records](#authoritative-records). Record decisions, completed
work, verification results and skips, unresolved questions, outstanding parent
requirements, and the next action.
Include the branch and whether changes are local, committed, or published so
the next session can locate the actual work. State the active slice, its current
phase, whether that phase and slice execution are complete or still in progress,
the separate verification/publication/delivery milestones, and any pending
maintainer design acceptance or issue-closure decision.
This handoff marks the session's end; it is needed even when work pauses partway
through a phase. A brief exchange or a phase transition alone does not require
ending the session.

If the session covered several slices, identify each slice and its resulting
state; post the relevant handoff details in each execution issue. Link shared
context rather than duplicating it. A slice-completion comment from earlier in
the session can be linked from the handoff without repeating its evidence.

## Exceptions

The maintainer may grant scoped exceptions to this workflow, but interface
design review and explicit acceptance remain mandatory under the current
policy. The agent cannot bypass the review or mark that phase not applicable.
Individual review items may be made optional only after prompting for and
receiving explicit maintainer approval. A general instruction to simplify the
work does not waive this gate.

For other exceptions, record the scope, any brief reason supplied, and the
requirements that still apply in the relevant issue. The maintainer need not
justify an exception. Other phases may be marked not applicable as an ordinary
judgment with a recorded reason; that does not remove required verification or
permit unsupported completion claims. Exceptions apply only to the stated work.

Waiving this workflow does not automatically waive Issue-first, branch,
verification, or merge requirements; overrides of those rules must be explicit.

## Workflow Review

Record proposed process improvements and their evidence in a relevant GitHub
issue. Distinguish proposals from accepted changes. The current workflow
remains mandatory until the maintainer explicitly approves a change or withdraws
the requirement. Completing a slice or issue does not change repository policy.
