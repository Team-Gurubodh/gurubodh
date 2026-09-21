---
name: slice-session
description: Restore, plan, and hand off Gurubodh GitHub issue work using its issue records and current slice phase. Use at session entry, resumption, or pause; unrelated read-only questions do not need this skill.
---

# Slice Session

Use the [slice workflow](../../../docs/development/slice-workflow.md) as the
process authority. This skill helps restore and record context.

## Start or Resume

1. Read the complete issue and available discussion, accepted decisions, and
   latest handoff. If the slice has a sub-issue, read its execution records and
   the linked parent coverage. Use [github-workflow](../github-workflow/SKILL.md)
   for retrieval and issue operations.
2. Inspect the branch, worktree, commits, and any PR named in the handoff. Compare
   recorded state with actual files; preserve unrelated or uncommitted work.
3. Identify the active slice, phase, and remaining parent requirements. State
   the intended session outcome. Distinguish proposals from accepted designs;
   locate the acceptance boundary and unresolved questions before selecting work.
4. Use the workflow's [activity route](../../../docs/development/slice-workflow.md#reading-route)
   for the current phase. Resume accepted work without requesting the same
   acceptance again; changed designs follow the design-review route.

If no slice exists, prepare its outcome, exclusions, mapped requirements,
acceptance criteria, uncertainties, and verification approach using the
[parent coverage format](../../../docs/development/templates/slice-records.md#parent-coverage-and-slice-plan).
Include constraints from the full issue, not just its acceptance checkboxes.

## Keep Execution Records Useful

Update the existing parent coverage instead of starting another checklist.
Preserve stable IDs when splitting work. Link sub-issue execution evidence back
to the parent summary using the workflow's
[ownership split](../../../docs/development/slice-workflow.md#lightweight-slice-checklist).

At a phase transition, compare the actual outcome with the
[phase table](../../../docs/development/slice-workflow.md#phase-outcomes).
Record evidence, skips, and remaining work where the workflow calls for them.
Use the [slice-completion format](../../../docs/development/templates/slice-records.md#slice-completion)
after reconciliation; keep the session open if work continues.

## Pause or Transfer

Prepare the [handoff format](../../../docs/development/templates/slice-records.md#session-handoff)
from actual checkout and issue state. Follow
[session exit](../../../docs/development/slice-workflow.md#session-entry-and-exit)
for required content and record ownership. Link earlier evidence rather than
copying it. Include enough branch/commit/PR information for another contributor
to find the work, even when nothing has been committed or published.

Post the handoff to its execution issue and verify the posted content. If issue
access fails, preserve the prepared text locally and report the unposted record
and location; do not claim it was posted. Keep publication and delivery pending
unless there is evidence for them.
