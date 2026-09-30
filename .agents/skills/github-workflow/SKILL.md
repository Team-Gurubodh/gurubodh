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

## Publish Specifications and Decisions

Publish the synthesis prepared by the discovery skill under the workflow's
[approval rules](../../../docs/development/slice-workflow.md#requirements-and-approval).
This skill records requirements and design decisions; it does not decide them.

1. Retrieve current remote content. Update the parent's existing requirements/
   coverage record and the owning issue's execution records; preserve unrelated
   content and stable requirement IDs. Link detailed records instead of copying
   them between parent and sub-issue.
2. Check the prepared record against
   [Requirements and Approval](../../../docs/development/slice-workflow.md#requirements-and-approval)
   for its version, status, acceptance scope, and any material revision.
   Use the corresponding [record format](../../../docs/development/templates/slice-records.md).
3. Publish the prepared body file. Retrieve the saved body and compare it with
   the file, including links and preserved unrelated text. Apply the workflow's
   [readback and recovery rules](../../../docs/development/slice-workflow.md#requirements-and-approval)
   to determine publication status and whether implementation may proceed.

Before retrying an uncertain write, check whether the record already exists
to avoid duplicate publication. Reuse valid publication authorization on resumption.

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

When closure is not authorized, use `Refs #<number>` and keep closing keywords
away from issue references in PR descriptions and commit messages. Negating a
closing phrase does not prevent GitHub from interpreting it as a closing link.
After publication and before merge, inspect `gh pr view <number> --json
closingIssuesReferences`; verify that the listed issues match the authorized
closure scope. Remove unintended closing links and verify the result before
merging. If an issue was closed unintentionally, restore its intended state and
record the correction; do not report whole-issue completion.

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
