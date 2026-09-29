# Slice Development Workflow

<record_type>workflow_guide</record_type>
<status>active</status>

This document defines the required process for GitHub issues. The [AGENTS.md](../../AGENTS.md)  file delegates this responsibility here. Supporting skills explain how to carry out activities for the slice workflow. Supporting skills do not introduce policy or approval gates.

## Reading Route

Read this workflow, then read slice-session [skill](../../.agents/skills/slice-session/SKILL.md). Restore the issue context and select resources for the active phase. If you do not know how to discover skills automatically, open the linked SKILL.md files directly. Read technical and historical references only when needed.

| Activity | Skill and references |
| --- | --- |
| Start, resume, or pause | [slice-session](../../.agents/skills/slice-session/SKILL.md); complete issue/discussion, accepted decisions, latest handoff; [session requirements](#session-entry-and-exit) |
| Discover requirements and plan coverage | slice-session; [requirements and approval](#requirements-and-approval), [interview protocol](interview-protocol.md), [coverage](#requirement-coverage), applicable goals/contracts |
| Review initial or materially changed design | [slice-design-review](../../.agents/skills/slice-design-review/SKILL.md); [design contract](#interface-design-review), existing implementation and applicable technical references |
| Prepare tests and implement | [phase outcomes](#phase-outcomes), accepted design and questions; component README and relevant contracts/tests |
| Verify and reconcile | [verification](#verification-and-delivery-status), [reconciliation](#slice-reconciliation); component verification commands and real integration boundaries |
| Operate on issues, branches, commits, Projects, or PRs | [github-workflow](../../.agents/skills/github-workflow/SKILL.md), [GitHub conventions](github-workflow.md); optional [command tutorial](git-github-cli-workflow-tutorial.md) |
| Publish, integrate, or close | github-workflow; [publication and integration](#publication-and-integration), [whole-issue completion](#whole-issue-completion) |

Use the required [record formats](templates/slice-records.md) for specifications, coverage, plan/design acceptance, slice completion, and handoffs. The sections below outline this content. Formats are simple aids, not extra gates.

## Core Terms and Their Relationship

A GitHub issue defines the overall scope. Break that scope into slices, advance each slice through phases, and use sessions to do the work.


| Term | Definition | When it is complete or ends |
| --- | --- | --- |
| Slice | A bounded unit of an issue's scope. It has a clear outcome, explicit exclusions, mapped requirements, and acceptance criteria. | Slice-Work is complete when you meet its acceptance criteria, record verification evidence, and reconcile its contribution to parent requirements in a slice-completion record. Delivery and issue closure are tracked separately. |
| Phase | A named stage of work within a slice. It produces a required outcome that enables further work. Examples include Planning and Interface Design. | A phase ends when you meet its required outcome and any acceptance gate. Interface design always needs maintainer acceptance. You may mark other phases not applicable if you record a reason. New findings may require you to revisit a phase. |
| Session | A work session by a contributor or agent. It starts when you restore context and state an intended outcome. It ends with a handoff when you pause work or transfer responsibility. | A session ends at the recorded stop or handoff point, even if the active phase or slice remains incomplete. |

A session can span multiple phases or slices, and a single slice can cover several sessions. A chat exchange or phase transition alone does not end a session. Always record a handoff when pausing or transferring work. Finally, ending a session does not mark a phase, slice, or issue as complete.

## Applicability

This workflow is mandatory for all GitHub issue work in this repository, effective September 18, 2026. Apply it through every stage—from planning and implementation to verification, reconciliation, whole-issue review, and handoff. No task size or type makes it optional. You can scale phase outcomes to the task, but you must keep the mandatory design review and maintainer acceptance gate.

Only an explicit maintainer instruction can grant a scoped workflow [exception](#exceptions). Even then, design-review protections still apply. Record any [exception](#exceptions) in the relevant GitHub issue.


## Authoritative Records

The parent GitHub issue and its discussion track all scope, progress, and verification records. Maintain the [coverage checklist](#requirement-coverage) there. Project board status simply reflects that progress; see [Projects tracking](github-workflow.md#projects-tracking).

From your first session, record every session handoff as a comment in the GitHub issue. Post in the parent issue unless the slice has its own sub-issue. If it has a sub-issue, post the handoff there and link back to the parent's coverage checklist. Keep the parent issue updated with links to all sub-issue comments.

Keep current slice designs, decisions, execution evidence, and handoffs in GitHub issues. When a slice has a sub-issue, follow the ownership split under [Lightweight Slice Checklist](#lightweight-slice-checklist). Do not keep duplicate execution records across the parent and sub-issue.

Keep tentative proposals separate from accepted decisions. Maintain one current requirements coverage record in the parent issue. Record each complete design, decision, and verification result once in its owning issue. Future acceptance, completion, and handoff records should link to that source instead of repeating long narratives or evidence. Repeat only the essential current-state fields each record requires, even when unchanged. Otherwise, state only new facts or status updates.

A link alone cannot prove a new acceptance, verification result, or milestone. Always list the subject, version or revision, and current status next to the link.

Recording an item once does not prevent you from replacing it with a consolidated version. Just name what it supersedes and keep the acceptance history under [requirements and approval](#requirements-and-approval). Once implemented, record lasting technical decisions into interface, schema, or decision documentation. Do not create competing copies of the scope.

## Requirements and Approval

Before proposing new or modified scope, restore the issue discussion, accepted decisions, relevant docs, and code facts. Requirements discovery must cover the problem, user journey, success metrics, boundaries, inputs, outputs, failure behavior, constraints, and acceptance examples. Reuse known answers, ask about key gaps or contradictions, and explain any dimension that does not apply. Use [slice-session](../../.agents/skills/slice-session/SKILL.md) and the shared [interview protocol](interview-protocol.md) to conduct discovery.

Present a versioned specification with stable requirement IDs, constraints, exclusions, acceptance criteria, examples, and categorized questions. The maintainer must explicitly approve this specification before you record it as accepted scope. A saved proposal remains a draft until approved. Silence, elapsed time, and draft publication do not count as acceptance.

The specification states **what** to deliver. The implementation plan states **how** to deliver those requirements through slices, design, and verification. The maintainer must accept the active slice's plan and design, usually in a single confirmation naming both subjects and versions.

If the plan was already accepted and has not changed, it does not need re-approval. However, you still need separate approval for the design. A roadmap assigns requirements to slices, but it does not approve a slice's design in advance.

The normal sequence follows these steps:

1. Accept and publish the specification.
2. Accept and publish the active-slice plan and design.
3. Prepare tests and begin implementation.

When resuming work, reuse any valid recorded approvals for their stated scope. Then, pick up at the missing decision or phase.

If design discovery reveals a product question, pause affected design work. Return to the requirement and get approval for its revised spec before making dependent design decisions. Keep unrelated accepted decisions intact.

Each key revision must list:

- The changed requirement IDs or decisions
- The reason for the change
- The record it replaces
- The approval required

Earlier approvals apply only to their original version and scope.

For each publication, read back the saved record and compare it with your intended text. Check both the acceptance scope and any preserved content. A failed write is unsaved. A failed read-back leaves publication unverified.

If a write or read-back fails:

- Save the exact text and its status locally.
- Restore the current remote content.
- Retry within your existing authorization.

Keep accepted-but-unsaved discussion distinct from recorded acceptance. Do not start implementation until you publish and verify all required acceptance records.

### Handling Unanswered Questions

Discover requirements with [slice-session](../../.agents/skills/slice-session/SKILL.md) and design with [slice-design-review](../../.agents/skills/slice-design-review/SKILL.md). Both share the [interview protocol](interview-protocol.md). The rules below show how unanswered questions impact dependent work and when discovery is complete enough to present a proposal.

For both requirements and design, separate facts, maintainer decisions, agent recommendations, and unresolved assumptions. Classify each open question, map affected dependencies, and state what can move forward:

- A **blocking** question can alter behavior, contracts, or verification. It stops dependent design and implementation. Resolve it and get approval before starting that work.
- A **nonblocking** question does not change the contract or verification of current work. Record why the work is independent and when you need the answer. Reclassify the question if its impact changes.

An optional preference may include a proposed default, but silence does not make it an approved decision. Discovery ends once you can state, verify, and approve the design, and every remaining question has a classification, clear scope, and target resolution point.


## Phase Outcomes

| Phase | Outcome needed to advance |
| --- | --- |
| Planning | Accepted specification; proposed slice outcome, exclusions, mapped requirements, acceptance criteria, uncertainties, and verification approach |
| Interface design | Active-slice plan and concrete design explicitly accepted under [Interface Design Review](#interface-design-review); acceptance scope, approved optional items, and classified questions published and verified before implementation |
| Test preparation | Reviewable success/failure cases, independent expectations, fixtures, and verification commands; executable tests where appropriate |
| Implementation | Reviewable changes satisfying the agreed contract, with relevant checks passing |
| Integration verification | Evidence using real applicable boundaries, reconciliation against parent requirements, and a slice-completion record; a session handoff only if the session also ends |

### Interface Design Review

Before coding, inspect the current code and present your design in chat for maintainer review. Show the contract and the supporting code structure. Clearly mark existing behavior, proposed changes, and open questions.

Before finalizing the proposal, investigate compatibility, abstractions and their responsibilities, interfaces, failure semantics, persistence, operational behavior, and tradeoffs. Use [slice-design-review](../../.agents/skills/slice-design-review/SKILL.md) and the [interview protocol](interview-protocol.md) to resolve key choices. Reuse settled answers and explain skipped topics. Handle routine technical details using existing conventions and the accepted design.

Get explicit maintainer approval for the active slice's plan and design before starting implementation. Record the confirmation along with its source, subjects, versions, and scope under [requirements and approval](#requirements-and-approval). Spec approval does not count as design acceptance. You cannot skip or mark this review phase as not applicable.

| Review area | Details to present |
| --- | --- |
| Modules | Names and paths of modules being added or edited, affected abstractions within them, and why the change belongs there. |
| Abstractions and responsibilities | Classes, interfaces, data types, or other relevant abstractions being added or edited; their main responsibilities, and changes from the existing design. |
| Functions and interfaces | Functions being added or edited, with proposed signatures, parameter and return types, relevant errors, and side effects. Show before and after for changed interfaces and contracts. If the same change applies to several internal functions, list them and explain the shared change to their signatures and behavior once. Explain any differences separately. |
| Collaboration | Which abstractions call or depend on which others, what data crosses each boundary, and who owns validation, orchestration, persistence, or other relevant responsibilities. |
| Contract and examples | Inputs, outputs, ownership, validation, errors, compatibility, and relevant cross-component behavior, illustrated by typical success and relevant failure cases. |
| Rationale and open decisions | Assumptions, alternatives considered, tradeoffs, the recommendation and its reasons, and questions requiring maintainer judgment. |

Use a module or abstraction table with short signature sketches where helpful. Add a sequence diagram or interaction example to clarify how components collaborate. Show how the active slice changes behavior and code structure, referencing accepted requirements and existing contracts.

Reference unchanged background details rather than repeating them. Describe new or changed contracts, responsibilities, failure behavior, compatibility, and key tradeoffs directly in the proposal. For major refactors, group repeated mechanical edits only if you name the affected functions, describe the shared transformation, and explain any changed contracts or failures. Include representative success and failure examples, but keep full test output in verification records.

Match detail to the slice's needs—there is no fixed word limit. Address every review area listed above. If an area seems unnecessary, explain why and ask the maintainer to approve skipping it. Record that approval in the issue. If prose-only changes require no code updates, state that no functions change. Finally, confirm when existing abstractions suffice instead of creating new ones to fill out the template.

Incorporate the maintainer's feedback from chat. Before implementation, publish one complete, identified version of the accepted design in the parent or execution sub-issue under [Authoritative Records](#authoritative-records). If that complete proposal is already published and remains current, a brief acceptance comment can link to it. If the proposal exists only in chat, publish the full accepted design and append the acceptance fields below, or link to a separate acceptance record.

Both publication paths must record:
- Maintainer confirmation and source
- Accepted plan, design versions, and scope
- Exact clarifications or changed sections
- Superseded records
- Approved optional items
- Unresolved questions, affected work, and allowed independent work

Clarifications that materially change the accepted contract must follow the versioning and approval rules under [requirements and approval](#requirements-and-approval). Calling a change a "clarification" does not bypass these rules.

If the linked proposal and clarifications cannot reconstruct the accepted design, publish a single consolidated version. Include an explicit supersession link and preserve the acceptance history. Link existing specifications instead of copying them.

Classify remaining questions under [discovery questions](#discovery-questions). Publish and verify the complete design and its acceptance record before starting implementation.

Independent work within the same slice may proceed only if the maintainer's accepted design explicitly covers it and no unresolved blocking question blocks it. The acceptance record must define that boundary. Future slices require their own concrete design records; linking this workflow alone is not enough.

If implementation reveals a material change to reviewed interfaces, responsibilities, or collaboration, pause to discuss the design and get approval for the updates. Update the issue record before making that change.

### Advancing Through Phases

Advance only when you establish the current phase's outcome. Implementation requires settled acceptance criteria and contracts, recorded design approval, and a verification plan—all within the user's authorization. Honor dependency gates recorded in relevant issues before starting dependent work.

Ask the maintainer about unresolved product choices, scope changes, or reserved decisions. You do not need repeated permission for routine technical choices or progress within an accepted design. Other phases can be brief or marked not applicable if you record a reason under [Exceptions](#exceptions).

For refactoring, clearly define the behavior that must remain unchanged. Use mocks or fakes to isolate dependencies and test failures where helpful. Use real validators, storage adapters, or integration boundaries early; mock agreement alone does not prove integration correctness. Scale your checks to the change and follow the issue's verification requirements.

## Lightweight Slice Checklist

Record these details for each active slice in the parent issue (unless the slice has its own sub-issue):

- Slice ID, outcome, and exclusions.
- Covered requirement references and acceptance criteria.
- Boundaries, accepted contracts, maintainer acceptance, approved optional review items, and open design questions with affected work.
- Verification plan, including integration checks.
- Current phase and status.
- Evidence of completion and remaining parent requirements.

Use this checklist in the existing GitHub issue templates. You do not need a separate template or sub-issue for every slice.

Start with slices in the parent issue. Promote a slice to a sub-issue when it needs independent ownership, substantial separate discussion, or its own delivery tracking. Keep its slice ID and parent requirement mapping. Multiple sessions alone do not require a sub-issue.

After promotion:

- The parent keeps the slice ID, brief outcome/exclusions summary, requirement mapping, current phase and status, remaining parent obligations, and links to the sub-issue and its verification evidence.
- The sub-issue owns the detailed checklist, design record, questions, verification plan, execution discussion, and session handoffs. Link the existing parent discussion when moving ownership. Do not keep competing copies.

## Requirement Coverage

Before starting the first slice, read the entire parent issue and discussion. Check all requirements, constraints, and exclusions outside the acceptance-criteria boxes.

Assign stable requirement references, slices, statuses, and evidence in one parent checklist. Assign every requirement to a slice or explicit follow-up work. Do not leave any requirement unassigned. You may refine later slices, but keep traceability when splitting or regrouping them.

Tracking a requirement in another slice or issue does not remove it from the parent issue. The requirement stays open until evidence satisfies it or the maintainer explicitly approves removing it from scope. Record this scope decision in the parent. A follow-up link alone is not enough.

Use clear statuses like pending, in progress, partial, and satisfied. Mark a requirement satisfied only with implementation, documentation, and verification evidence. Shared requirements need both incremental evidence and a final check across the completed issue.

## Slice Reconciliation

After every slice:

1. Link evidence to the requirements it satisfies.
2. Mark partial progress and remaining work explicitly.
3. Identify uncovered requirements or new gaps and assign them to follow-up work. Get maintainer agreement before changing official scope.
4. Pick the next slice from remaining requirements.

After integration checks and cleanup, post a slice-completion comment in the slice issue. Include the slice ID, acceptance-criteria results, requirement mapping, current status, remaining parent work, and next steps.

Link to any earlier issue record that contains commands, test results, verifier name, skips with reasons, remaining uncertainty, and decisions. Include those details here only if you have not recorded them elsewhere. You do not need a separate verification comment. Briefly summarize new evidence or changed results and link to the source. Do not copy full test logs or long stories that exist elsewhere. This comment records that slice execution is complete. It does not end the session or close the issue.

If your session ends here, one comment can serve as both the slice-completion record and session handoff. Just include both sets of details and state clearly that the session is ending.

## Verification and Delivery Status

Record these milestones separately for each slice and the issue, with evidence
and any pending milestone made explicit:

| Status | Meaning and evidence |
| --- | --- |
| Implementation verified | The implementation or documentation satisfies its acceptance criteria and required checks, with evidence recorded. Changes may still be local and uncommitted. Identify who verified the work. The agent's evidence cannot replace the maintainer's final approval needed to close the issue. |
| Published for review | Reviewers can access the changes, usually in a pushed branch and linked PR. A status comment alone does not publish repository changes. |
| Delivered | The result reached its required target, with evidence—for example, merged into the main branch or deployed as required. Define that target in the issue. Do not assume delivery just because you completed verification, created a PR, or closed the issue. |

Use the component's documented checks: start with [repository commands](../../README.md#repository-commands), the [CMS README](../../apps/gurubodh-cms/README.md), the [content CLI README](../../tools/gurubodh-cli/README.md), or the relevant guide. Record commands, results, who verified them, and evidence.

For any skipped check, record exactly what was skipped, why, and the remaining uncertainty. A skip is not a pass. Resolve required verification gaps or get explicit maintainer approval before closing the issue.

These milestones do not need to happen in a fixed order. For example, you can publish a draft PR before finishing verification. Always distinguish between technical verification, maintainer confirmation, publication, delivery, and issue closure. None of these statuses gives you permission to merge or deploy.

## Publication and Integration

A slice may be ready for review while other issue requirements remain open. Prepare a linked PR describing the slice's scope, verification, documentation, and remaining work. Use the [PR template](../../.github/PULL_REQUEST_TEMPLATE.md) and [GitHub conventions](github-workflow.md#pull-requests). A draft PR can share unfinished work as long as you state its status accurately. Report the changes and any verification skips to the maintainer.

Use `Refs #<issue-number>` until whole-issue review and maintainer approval authorize closure under [Whole-Issue Completion](#whole-issue-completion). Only then can you use a closing reference.

Merge only after required checks and review pass. Agents need explicit maintainer instruction before merging, squashing, rebasing, or integrating into the target branch. Review approval, design acceptance, verification, publication, and issue closure do not count as instruction. After authorized integration, record delivery evidence and follow [branch cleanup](github-workflow.md#branch-cleanup).

## Whole-Issue Completion

Before asking to mark an issue complete, reread its full description and discussion. Compare every requirement against implementation, documentation, and verification evidence, including integration across separate slices. Every requirement must have evidence or explicit maintainer approval to remove it from scope. Do not silently defer anything.

Passing this review allows you to report verification evidence and request the maintainer's completion decision. Mark an issue complete and close it only after the maintainer explicitly confirms "implementation verified" and instructs you to close it. Record that confirmation and instruction in the issue. Your successful checks, design approval, publication, or delivery do not give this authorization. This rule applies to both sub-issues and parent issues.

If the maintainer authorizes closure while publication or delivery is pending, record those open steps and actions clearly. Closing an issue does not mean delivery has occurred, nor does it authorize a merge.

## Session Entry and Exit

When you start, read the full primary issue, past discussion, accepted decisions, and latest handoff comment. Identify the current slice and phase, then state your session goal. Use existing decisions rather than re-opening them without new evidence.

When you finish, post a handoff comment in the issue listed under [Authoritative Records](#authoritative-records). Provide a brief status update, including all of these fields even if they have not changed: active slice and phase; completion status for each; open requirement IDs, blockers, and questions with affected work; branch, commit, and PR status (local, committed, or published); separate verification, publication, and delivery milestones; pending spec, plan, design, verification, or closure decisions; and the exact next step. Clearly separate recorded acceptance from draft ideas, unsaved discussions, or unverified changes.

Next, summarize what changed in this session: decisions, completed work, test results, and new or resolved questions. Link to detailed decisions and evidence recorded earlier, even from the same session. Only include commands, observed results, verifiers, skipped steps, remaining risks, and related decisions here if they are not recorded elsewhere; you do not need a separate verification comment. For unchanged items, link to the official records and note that they are unchanged rather than repeating the details. Your handoff must clearly state the current status and next step so the reader does not have to guess from links. This handoff ends the session, even if you stop halfway through a phase; a short conversation or phase shift alone does not mark the end.

If your session covered multiple slices, list each slice and its final state. Post the specific handoff details in each execution issue, and link shared context instead of repeating it. If you posted a slice-completion comment earlier in the session, link to it from the handoff instead of retyping the evidence.

## Exceptions

The maintainer may grant limited exceptions to this workflow, but interface design review and explicit approval remain mandatory under current policy. The agent cannot skip the review or mark that phase as not applicable. You can make individual review items optional only after asking for and receiving explicit maintainer approval. A general request to simplify the work does not remove this requirement.

For other exceptions, record the scope, any brief reason given, and the requirements that still apply in the relevant issue. The maintainer does not need to justify an exception. You may mark other phases as not applicable as a normal judgment with a recorded reason; this does not remove required testing or allow unverified claims of completion. Exceptions apply only to the specified work.

Waiving this workflow does not automatically waive Issue-first, branch, testing, or merge rules; any override of those rules must be explicit.

## Workflow Review

Record proposed process improvements and their evidence in a relevant GitHub issue. Separate proposed changes from accepted ones. You must follow the current workflow until the maintainer explicitly approves a change or drops the requirement. Finishing a slice or issue does not change repository policy.
