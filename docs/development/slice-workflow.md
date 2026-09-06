# Slice Development Workflow

<record_type>workflow_guide</record_type>
<status>provisional_pilot</status>

## Applicability

[Issue #289](https://github.com/Team-Gurubodh/gurubodh/issues/289) owns this
process pilot. The full phase workflow is mandatory only for the proofreading
and chunking profile-contract slice of
[#283](https://github.com/Team-Gurubodh/gurubodh/issues/283). Requirement
coverage, slice reconciliation, and whole-issue completion apply to all of
#283. Wider adoption requires an explicit maintainer decision after the pilot.

Work proceeds in small, verifiable slices. Each slice passes through planning,
interface design, test preparation, implementation, and integration
verification. A phase may be brief or marked not applicable, with a reason
recorded. Sessions and phases need not have matching boundaries.

Use this guide alongside the [GitHub workflow](./github-workflow.md).
The current handoff is [Task-018](../tasks/018-slice-development-pilot.md);
the rationale is [Decision-0008](../decisions/0008-slice-development-pilot.md).

## Authoritative Records

The parent GitHub Issue and its discussion define technical scope. Maintain
one coverage checklist there, using stable requirement references, assigned
slices, status, and completion evidence. Include requirements and constraints
throughout the description, not just its acceptance-criteria checkboxes.

Task records hold session handoffs and link to the authoritative checklist.
Keep tentative proposals distinct from accepted decisions. Promote lasting
technical decisions into the appropriate interface, schema, or decision
documentation when implemented. Do not create competing copies of the scope.

## Phase Outcomes

| Phase | Outcome needed to advance |
| --- | --- |
| Planning | Bounded outcome, exclusions, mapped parent requirements, acceptance criteria, and known uncertainties |
| Interface design | Inputs, outputs, ownership, validation, errors, compatibility, and relevant cross-component behavior settled with examples |
| Test preparation | Reviewable success/failure cases, independent expectations, fixtures, and verification commands; executable tests where appropriate |
| Implementation | Small reviewable changes satisfying the agreed contract, with relevant checks passing |
| Integration verification | Evidence using real applicable boundaries, reconciliation against parent requirements, and a session handoff |

Implementation begins only after acceptance criteria, relevant contracts, and
the verification approach are settled, within the user's authorization.
Interface changes discovered during implementation return to design and test
preparation as needed. Ask about unresolved product choices, scope changes, or
decisions reserved for the maintainer; ordinary technical choices and progress
within approved scope do not require repeated permission.

For refactoring, characterize behavior that must survive the change. Use mocks
or fakes to isolate dependencies and exercise failures where helpful. Use real
validators, storage adapters, or other applicable integration boundaries early;
mock agreement alone does not establish integration correctness. Scale checks
to the change and follow the issue's required verification.

## Lightweight Slice Checklist

Record these fields in the parent issue for each active slice:

- Slice ID, outcome, and exclusions.
- Covered requirement references and acceptance criteria.
- Boundaries, contracts, and open design questions.
- Verification plan, including applicable integration checks.
- Current phase, status, and blocking questions, if any.
- Completion evidence and remaining parent requirements.

This is a pilot checklist, not a replacement GitHub issue template. Reusable
template changes wait for the retrospective and adoption decision.

Start with slices in the parent issue. Promote a slice to a sub-issue when it
needs independent ownership, substantial separate discussion, or its own
delivery and dependency tracking. Preserve its slice ID and parent requirement
mapping. Multiple sessions alone do not require a sub-issue. The sub-issue owns
execution detail; the parent retains coverage and completion evidence.

## Requirement Coverage

Before implementing the first slice, read the full parent issue and available
discussion and assign every requirement to a slice or explicitly identified
subsequent work. No requirement may remain unassigned. Proposed later slices
may be refined; preserve traceability when splitting or regrouping them.

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

Partial PRs use `Refs #<issue-number>`. A completed slice does not close its
parent issue. The handoff states both what the slice completed and what the
parent issue still requires.

## Whole-Issue Completion

Before declaring the parent issue complete, reread its entire description and
discussion. Compare every requirement against implementation, documentation,
and verification evidence, including integration across separately completed
slices. Every requirement must be satisfied with evidence or explicitly
removed from scope by the maintainer. Nothing may be silently deferred.

Account for all required checks. Record skipped verification and its reason;
a skipped check is not a pass. If required behavior remains unverified,
resolve the gap or obtain an explicit maintainer decision before completion.

#284 implementation waits until #283 passes this review. Consulting #284 to
assess downstream needs is allowed. A completion review does not authorize
merging; the existing explicit merge-authorization requirement still applies.

## Session Entry and Exit

At entry, read the authoritative issue and latest handoff, identify the active
slice and phase, and state the intended session outcome. Reuse accepted
decisions instead of reopening them without new evidence.

At exit, record decisions, completed work, verification results and skips,
unresolved questions, outstanding parent requirements, and the next action.
Include the branch and whether changes are local, committed, or published so
the next session can locate the actual work.

## Exceptions

The user may waive or simplify this workflow for a specified task or slice.
Record the exception's scope, any brief reason supplied, and the requirements
that still apply. The user need not justify it. Exceptions apply only to the
stated work. Marking a phase not applicable is an ordinary judgment, recorded
briefly, and does not itself require permission.

Waiving this workflow does not automatically waive Issue-first, branch,
verification, or merge requirements; overrides of those rules must be explicit.

## Pilot Review

After the selected slice completes, review which steps helped, which added
unnecessary overhead, and what was missing. Record evidence and proposed
adjustments under #289. The retrospective may inform the remaining #283 work
before that issue is complete.

Pilot completion, process adoption, and parent-issue completion are separate
milestones. Obtain maintainer agreement before making the revised workflow the
repository default or introducing reusable issue-template changes.
