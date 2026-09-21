---
name: github-workflow
description: Carry out Gurubodh issue, branch, commit, PR, Projects, and evidence operations under the accepted slice workflow. Use when those GitHub or repository operations are needed; unrelated read-only questions do not need this skill.
---

# GitHub Operations

Use [AGENTS.md](../../../AGENTS.md) for entry and authority, the
[slice workflow](../../../docs/development/slice-workflow.md) for lifecycle
and authorization, and [GitHub conventions](../../../docs/development/github-workflow.md)
for mechanics. This skill assists those activities; it defines no separate
policy hierarchy or completion gate.

## Read and Update Issues

Read the issue body and full available discussion; `gh issue view <number>
--json title,body,comments,projectItems` provides them with Project membership.
Equivalent connected tools are suitable. For an issue creation request, choose
the repository template and prepare its scope and verification content.

For coverage changes, retrieve the current body, modify the existing checklist,
and preserve unrelated content. For comments or PR descriptions, prepare exact
Markdown in a file and pass `--body-file`; avoid shell interpolation of prose.
Post to the parent or execution sub-issue selected by the workflow and verify
the returned URL/content. Use the [record formats](../../../docs/development/templates/slice-records.md).

Inspect Project membership and current field values. Follow
[Projects tracking](../../../docs/development/github-workflow.md#projects-tracking)
using the board's actual status options and completion conditions. Check whether
automation already applied the transition before updating it. Report access
failures and pending updates rather than claiming synchronization.

## Locate and Preserve Work

Inspect `git status --short --branch`, the branch history, and any recorded PR
before switching branches. Resume the recorded issue branch when appropriate;
otherwise fetch the base and create the branch using
[branch conventions](../../../docs/development/github-workflow.md#branches).
Preserve existing work; never reset or stage unrelated changes to simplify setup.

## Prepare Commits and PRs

Inspect the diff against accepted scope and recorded verification. Stage only
intended files, review the staged diff, and use the repository's
[commit syntax](../../../docs/development/conventional-commits.md).

Prepare the full [PR template](../../../.github/PULL_REQUEST_TEMPLATE.md).
Describe the concrete change, slice scope, actual checks/skips, documentation,
and outstanding requirements; link issue evidence. Select the issue reference
under [publication and integration](../../../docs/development/slice-workflow.md#publication-and-integration).
Publish within the user's authorization, marking unfinished work as draft.
Verify the branch, PR URL, title/body, and check results after publication.

A failed command is not evidence of a completed action. Preserve useful local
artifacts and report any blocked publication or verification accurately.

## Integrate, Clean Up, and Close

Consult [integration authorization](../../../docs/development/slice-workflow.md#publication-and-integration)
and current required checks/review before any integration action. After an
authorized merge, verify its result and follow
[branch cleanup](../../../docs/development/github-workflow.md#branch-cleanup).
Compare intended work with the merged result before deleting branches,
especially after a squash merge or additional local commits.

For closure, use [whole-issue completion](../../../docs/development/slice-workflow.md#whole-issue-completion).
Record delivery, completion instructions, and pending milestones as applicable;
verify the resulting issue and board state. Command examples are in the optional
[CLI tutorial](../../../docs/development/git-github-cli-workflow-tutorial.md).
