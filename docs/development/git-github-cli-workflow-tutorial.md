# Git and GitHub CLI Workflow Tutorial

Optional command examples for the [GitHub conventions](github-workflow.md).
The [slice workflow](slice-workflow.md) owns lifecycle and authorization.
Read it before starting issue work. Examples use issue #25; substitute your
issue, branch, filenames, and actual evidence.

## Restore Context

```bash
gh --version
gh auth status
git status --short --branch
gh issue view 25 --json title,body,comments,projectItems
```

If authentication is missing, use `gh auth login`. Preserve unrelated work in
the checkout. Follow [slice-session](../../.agents/skills/slice-session/SKILL.md)
to identify the active phase and intended outcome from the issue and handoff.

When creating an authorized new issue, select the appropriate issue template
in GitHub or prepare its content in a file:

```bash
gh issue create --title "[Docs]: clarify contributor commands" \
  --label "type: docs" --body-file /tmp/new-issue.md
```

## Create or Resume a Branch

For new work, fetch the base and create the issue branch:

```bash
git fetch origin main
git switch -c issue-25-contributor-commands origin/main
```

For existing work, use its recorded branch instead:

```bash
git switch issue-25-contributor-commands
```

## Plan and Review the Design

Use [slice-session](../../.agents/skills/slice-session/SKILL.md) for requirements
discovery and coverage. Obtain acceptance of an identified specification, then
publish and verify it. Use
[slice-design-review](../../.agents/skills/slice-design-review/SKILL.md) to prepare
the active slice's plan and concrete design for acceptance. Name both subjects
and versions when accepted together, then publish and verify that acceptance
before implementation. Follow the workflow's
[approval sequence](slice-workflow.md#requirements-and-approval) and
[record formats](templates/slice-records.md); reuse valid recorded acceptance
on resumption.

After preparing and reviewing the appropriate record, post it:

```bash
gh issue comment 25 --body-file /tmp/slice-design.md
```

Use a proposal status until acceptance is obtained; posting a proposal does not
accept it. On resumption, use the already recorded acceptance for unchanged work.

## Prepare Checks, Implement, and Reconcile

Establish success/failure cases and verification commands, then implement the
accepted design. Inspect changes and run the relevant component checks:

```bash
git diff
git diff --check
```

For example, CMS changes use the [CMS guide](../../apps/gurubodh-cms/README.md);
these documentation commands alone do not verify application behavior.

Record actual evidence and skips, reconcile requirements, and post a completion
record when the [slice criteria](slice-workflow.md#slice-reconciliation) are met:

```bash
gh issue comment 25 --body-file /tmp/slice-completion.md
```

Update the existing parent coverage checklist, preserving the rest of the issue.
For a reviewed full issue body saved locally:

```bash
gh issue edit 25 --body-file /tmp/issue-body.md
```

## Commit and Publish

Stage only files belonging to the change, review, and commit:

```bash
git add docs/development/git-github-cli-workflow-tutorial.md
git diff --cached
git commit -m "docs(github): clarify contributor commands (#25)"
git push -u origin issue-25-contributor-commands
```

Prepare the complete PR template, replacing `Refs #` with `Refs #25`, filling
all applicable sections, and checking only verified items:

```bash
cp .github/PULL_REQUEST_TEMPLATE.md /tmp/pr-body.md
```

After editing and reviewing that file:

```bash
gh pr create --base main --head issue-25-contributor-commands \
  --title "docs(github): clarify contributor commands (#25)" \
  --body-file /tmp/pr-body.md
gh pr view --json number,title,state,isDraft,reviewDecision,statusCheckRollup,url
gh pr checks
```

Use `--draft` for unfinished work. Follow
[publication and integration](slice-workflow.md#publication-and-integration)
for readiness and closing references. Review feedback is handled on the same
branch; material design changes return to the design phase.

## Pause or Transfer Work

Prepare a handoff with the real phase, branch/commit, results, pending decisions,
and next action using [slice-session](../../.agents/skills/slice-session/SKILL.md).
This applies at any stopping point, even before implementation or publication:

```bash
gh issue comment 25 --body-file /tmp/session-handoff.md
```

If the issue belongs to Projects, follow
[Projects tracking](github-workflow.md#projects-tracking) and verify its status.

## Integrate and Clean Up

Apply the workflow's [integration conditions](slice-workflow.md#publication-and-integration)
before running a merge command. After explicit authorization and required checks
and review, an example squash merge is:

```bash
gh pr merge 123 --squash
```

Verify merge and inspect the checkout before cleanup:

```bash
gh pr view 123 --json state,mergedAt,mergeCommit,url
git status --short --branch
git fetch origin
git log --oneline origin/main..issue-25-contributor-commands
```

Replace PR #123 with the real PR. Compare intended work, including any commits
added after merge, with the merged PR and target content. Squashed commits may
appear in the log even when their changes landed. Preserve any unmatched work.
Delete the remote branch if GitHub has not already removed it, after confirming
that it contains no additional work beyond the merged PR:

```bash
git push origin --delete issue-25-contributor-commands
```

Then update the local target and delete the local issue branch:

```bash
git switch main
git pull --ff-only
git branch -d issue-25-contributor-commands
```

If `-d` fails after a squash merge, follow the preservation checks in
[branch cleanup](github-workflow.md#branch-cleanup) before substituting `-D`.
Record delivery and any board update. Issue closure follows
[whole-issue completion](slice-workflow.md#whole-issue-completion); do not infer
it from merge or branch deletion.
