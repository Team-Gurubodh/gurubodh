# Git And GitHub CLI Workflow Tutorial

<record_type>workflow_tutorial</record_type>
<status>active</status>

This tutorial walks through the Gurubodh issue-first workflow using `git` and
the GitHub CLI, `gh`.

Use this document when you want the exact commands to follow. Use
`docs/development/github-workflow.md` when you want the shorter policy
reference.

## Prerequisites

Install and authenticate the GitHub CLI:

```bash
gh --version
gh auth status
```

If `gh auth status` says you are not logged in, run:

```bash
gh auth login
```

Confirm your local checkout is clean before starting new work:

```bash
git status --short --branch
```

If the output shows modified or untracked files, decide whether those changes
belong to the current issue before continuing.

## Start From An Issue

Create or select a GitHub issue before starting work.

Use the issue template that matches the work:

- Feature: new functionality or a meaningful capability.
- Bug Report: reproducible problem in existing behavior.
- Documentation: documentation-only work.
- Decision: process, product, workflow, or architecture choice.
- Task: scoped non-feature work such as cleanup, maintenance, migration,
  investigation, or enablement.

You can create issues in the GitHub UI, the GitHub VS Code extension, or with
`gh`.

Example documentation issue:

```bash
gh issue create \
  --title "[Docs]: add Git and GitHub CLI workflow tutorial" \
  --label "type: docs" \
  --body "Add a beginner-oriented tutorial for the issue-first workflow."
```

Example feature issue:

```bash
gh issue create \
  --title "feat: add seed-data import preview" \
  --label "type: feature" \
  --body "Add a preview step before importing seed data into the CMS."
```

After the issue is created, note its issue number. The examples below use issue
`#25`.

## Create A Branch

Start from the latest `main`:

```bash
git switch main
git pull --ff-only
```

Create a branch that includes the issue number and a short description:

```bash
git switch -c issue-25-git-github-cli-workflow-tutorial
```

Useful branch examples:

```bash
git switch -c issue-19-strapi-mcp-setup
git switch -c issue-22-seed-data-google-sheets-validation-scripts
git switch -c issue-25-git-github-cli-workflow-tutorial
```

## Make Changes

Work in the files that belong to the issue.

Check what changed:

```bash
git status --short --branch
git diff
```

For a docs-only issue, review Markdown and run the basic whitespace check:

```bash
git diff --check
```

For application or tooling changes, also run the commands documented for that
area. Examples:

```bash
make cms-build
gurubodh-seed-data --help
```

If a command cannot run, write down exactly what was skipped and why so the pull
request can include that note.

## Commit

Stage only the files that belong to the issue:

```bash
git add docs/development/git-github-cli-workflow-tutorial.md
git add docs/development/README.md CONTRIBUTING.md
```

Review staged changes:

```bash
git status --short
git diff --cached
```

Commit using Conventional Commits:

```bash
git commit -m "docs(github): add git and github cli workflow tutorial"
```

Common examples:

```bash
git commit -m "feat(seed-data): add google sheets validation scripts"
git commit -m "fix(cms): correct subject relation config"
git commit -m "docs(github): add pull request workflow"
git commit -m "chore(cms): enable strapi mcp setup"
```

## Push

Push the branch and set upstream tracking:

```bash
git push -u origin issue-25-git-github-cli-workflow-tutorial
```

After this command, GitHub can create a pull request from the branch.

## Open A Pull Request

Create a pull request with a Conventional Commit title:

```bash
gh pr create \
  --base main \
  --head issue-25-git-github-cli-workflow-tutorial \
  --title "docs(github): add git and github cli workflow tutorial" \
  --body "## Summary

Adds a beginner-oriented tutorial for the Gurubodh issue-first workflow using git and the GitHub CLI.

## Linked Issue

Closes #25

## Scope

- Adds docs/development/git-github-cli-workflow-tutorial.md.
- Links the tutorial from contributor documentation.

## Verification

- [x] Ran git diff --check.
- [x] Reviewed the tutorial commands locally."
```

Use `Closes #<issue-number>` when merging the pull request should close the
issue. Use `Refs #<issue-number>` when the pull request is partial progress.

## Check Pull Request Status

View the current pull request:

```bash
gh pr view --web
```

View important fields in the terminal:

```bash
gh pr view \
  --json number,title,state,isDraft,mergeable,reviewDecision,statusCheckRollup,url
```

Check CI status:

```bash
gh pr checks
```

The repository currently expects pull requests to pass the configured checks and
receive required review before merge.

## Update A Pull Request

If review asks for changes, edit the files, then commit and push again:

```bash
git status --short
git diff
git add <files>
git commit -m "docs(github): clarify workflow cleanup steps"
git push
```

The pull request updates automatically after the push.

## Merge

Merge only after required checks pass and required review is complete.

You can merge in the GitHub UI. Prefer the repository's normal merge method for
the pull request.

If maintainers allow CLI merges, use:

```bash
gh pr merge --squash --delete-branch
```

If branch protection prevents the merge, do not bypass it. Wait for the required
review or checks.

## Clean Up After Merge

After the pull request is merged and the remote branch is deleted, clean up your
local checkout:

```bash
git switch main
git fetch --prune
git pull --ff-only
```

Delete the local branch:

```bash
git branch -D issue-25-git-github-cli-workflow-tutorial
```

Confirm the repo is clean:

```bash
git status --short --branch
```

## Protect Work In Progress

If you have uncommitted work and need to pause it before starting another issue,
put it on a temporary branch and make a checkpoint commit:

```bash
git switch -c strapi-mcp-setup-and-seed-data-scripts
git add <files>
git commit -m "chore: checkpoint strapi mcp setup and seed data scripts - WIP"
```

Then switch back to `main` for the new issue:

```bash
git switch main
git pull --ff-only
```

Delete the checkpoint branch only after all intended work has landed on `main`.

## Split Work Across Multiple Issues

Sometimes one working branch contains changes for more than one issue. Do not
open one mixed pull request. Instead, use the WIP branch as a source and create
clean issue branches from `main`.

Example:

```bash
git switch main
git pull --ff-only
git switch -c issue-19-strapi-mcp-setup
```

Restore only the files for issue `#19`:

```bash
git restore --source strapi-mcp-setup-and-seed-data-scripts -- \
  apps/gurubodh-cms/config/server.ts \
  apps/gurubodh-cms/package.json \
  apps/gurubodh-cms/package-lock.json \
  apps/gurubodh-cms/types/generated/contentTypes.d.ts
```

Review, verify, commit, push, and open the pull request for issue `#19`.

Then create the second branch from current `main`:

```bash
git switch main
git pull --ff-only
git switch -c issue-22-seed-data-google-sheets-validation-scripts
```

Restore only the files for issue `#22`:

```bash
git restore --source strapi-mcp-setup-and-seed-data-scripts -- \
  tools/seed-data/README.md \
  tools/seed-data/scripts
```

Review, verify, commit, push, and open the pull request for issue `#22`.

Before deleting the checkpoint branch, confirm all intended work is represented
on `main`.

## Useful Commands

Show current branch and file state:

```bash
git status --short --branch
```

Show local branches:

```bash
git branch --list
```

Show recent commits:

```bash
git log --oneline --decorate -5
```

Show changed files:

```bash
git diff --name-status
```

Show staged changes:

```bash
git diff --cached
```

List open pull requests:

```bash
gh pr list
```

Open the current pull request in the browser:

```bash
gh pr view --web
```

List issues:

```bash
gh issue list
```
