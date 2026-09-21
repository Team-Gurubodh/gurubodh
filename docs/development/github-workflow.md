# GitHub Conventions

This guide owns GitHub mechanics. Use the [slice workflow](slice-workflow.md)
for phases, collaboration, authorization, verification, and completion.
The optional [CLI tutorial](git-github-cli-workflow-tutorial.md) shows commands.

## Setup

Prefer SSH; use HTTPS when SSH is unavailable:

```bash
git clone git@github.com:Team-Gurubodh/gurubodh.git
# HTTPS alternative:
# git clone https://github.com/Team-Gurubodh/gurubodh.git
cd gurubodh
```

Use [repository commands](../../README.md#repository-commands) to install the
relevant toolchain.

## Issues

Select the template matching the work:

| Type | Use |
| --- | --- |
| Feature | New functionality; start the title with `feat: ` |
| Bug Report | Reproducible behavior problems |
| Documentation | Documentation-only changes |
| Decision | Architecture, process, product, or workflow choices |
| Task | Scoped maintenance, migration, investigation, or enablement |

Describe the problem, intended outcome, affected area, acceptance criteria,
and verification. Templates help describe work; scope includes the entire
issue and its discussion under the [coverage rules](slice-workflow.md#requirement-coverage).
For bug work, reproduce the problem where practical before changing behavior.

## Projects Tracking

Using a GitHub Projects board is optional. The issue holds authoritative scope,
progress, and verification records under the
[slice workflow](slice-workflow.md#authoritative-records).

If an issue belongs to a board, keep its status aligned with actual progress
and that project's completion conditions. Use configured automation or update
it directly as part of the work; no separate maintainer request is needed for
each update. Verify the resulting status rather than assuming automation ran.
Move an issue to Done when those completion conditions are satisfied. Board
status does not replace the workflow's delivery and closure conditions.

## Branches

Create `issue-<number>-<short-description>` from the latest `main`. Inspect the
checkout first and preserve existing work. A freshly fetched `origin/main`
can be used as the branch base without changing the local `main` branch.
Use one branch per issue in normal work; keep PRs small and scoped to one issue.

See [AGENTS.md](../../AGENTS.md#essential-rules) for the dedicated-branch rule.
For an existing issue branch, resume it rather than creating a duplicate.

## Commits

Use [Conventional Commits](conventional-commits.md). Every commit message and
PR title must reference its issue:

```text
<type>(optional-scope): <summary> (#<issue-number>)
docs(agents): clarify instruction routing (#357)
```

Stage only intended files and inspect the staged diff before committing.

## Pull Requests

Use the full [PR template](../../.github/PULL_REQUEST_TEMPLATE.md), keeping all
sections and completing applicable content. Include the issue reference,
change and scope, verification results/skips, documentation changes, reviewer
guidance, and links to issue evidence. Check boxes only for work actually done.
Use the reference permitted by
[publication and integration](slice-workflow.md#publication-and-integration).

A PR can advance a slice without satisfying the whole issue. State remaining
requirements and whether the PR is a draft. Keep follow-up commits on its branch.

Reviewers check scope, behavior/documentation/tests, required checks, issue
coverage and evidence, recorded exceptions, authorization for closing references,
and absence of secrets or local-only files.

Inspect current GitHub rules for required checks and review; workflow files
alone do not establish branch protection. See [automation](automation.md).
Prefer squash merge for small PRs unless maintainers choose otherwise, subject
to the workflow's [integration authorization](slice-workflow.md#publication-and-integration).

## Branch Cleanup

After merge, delete the remote issue branch and then the local branch once all
intended work is confirmed preserved. Check for uncommitted work and additional
commits, and confirm the PR's merged state and content in the target branch.
Switch off the issue branch before deleting it.

Prefer `git branch -d`. A squash merge may cause Git to reject that deletion
because commit ancestry differs. Use `git branch -D` only after verifying that
all intended work is preserved in the target branch; do not discard later or
unmerged work. The [tutorial](git-github-cli-workflow-tutorial.md#integrate-and-clean-up)
shows the command sequence.
