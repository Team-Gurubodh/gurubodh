# GitHub Workflow

<record_type>workflow_guide</record_type>
<status>active</status>

This guide defines the default contribution workflow for Gurubodh.

For a beginner-oriented command walkthrough, see
`docs/development/git-github-cli-workflow-tutorial.md`.

## Principles

- Start from a GitHub issue.
- Keep each pull request scoped to one issue.
- Keep pull requests small enough to review carefully.
- Use `main` as the protected integration branch.
- Prefer SSH for GitHub access. Use HTTPS only as a fallback.

## First-Time Setup

Clone the repository with the project-specific SSH host alias:

```bash
git clone git@github.com-gurubodh:<OWNER>/gurubodh.git
cd gurubodh
```

If SSH is not available, use HTTPS:

```bash
git clone https://github.com/<OWNER>/gurubodh.git
cd gurubodh
```

Install the toolchain needed for the area you are changing. Common commands are documented in the root `README.md`.

## Issue-First Workflow

Create or select a GitHub issue before starting work.

Choose the issue template that matches the work type:

- **Feature** - new functionality or a meaningful capability. Feature issue
  titles should start with `feat: ` so they align with Conventional Commits.
- **Bug Report** - reproducible problems in existing behavior.
- **Documentation** - documentation-only changes.
- **Decision** - workflow, process, product, or architecture choices that need
  an explicit decision before implementation.
- **Task** - scoped non-feature work such as cleanup, maintenance, migration,
  investigation, or project enablement.

The issue should describe:

- The problem or goal.
- The expected outcome.
- The relevant project area.
- Any acceptance criteria or verification steps.

Use GitHub Projects to track issue status.

## Branches

Create a branch from the latest `main`:

```bash
git switch main
git pull --ff-only
git switch -c issue-<number>-short-description
```

Examples:

```bash
git switch -c issue-12-add-pr-template
git switch -c issue-18-configure-commitlint
git switch -c issue-21-document-ssh-setup
```

## Commits

Use Conventional Commits:

```text
<type>(optional-scope): <summary>
```

Examples:

```text
docs(github): add pull request workflow
ci(commitlint): enforce conventional commit messages
fix(cms): correct subject relation config
```

See `docs/development/conventional-commits.md` for details.

## Pull Requests

Open a pull request when the branch is ready for review.

Each pull request should:

- Link one issue with `Closes #<issue-number>` or `Refs #<issue-number>`.
- Explain the change in plain language.
- List verification performed.
- State whether documentation changed.
- Stay focused on one issue.

Use `Closes` only when merging the pull request should close the issue. Use `Refs` when the pull request is partial progress.

## Review

Reviewers should check:

- The pull request is linked to one issue.
- The scope is understandable and reviewable.
- Behavior, documentation, and tests match the stated goal.
- Required checks pass.
- No secrets or local-only files are included.

Authors should respond to review comments in the pull request and push follow-up commits to the same branch.

## Merge

Merge only after required checks pass and the required approval has been granted.

Prefer squash merge for small pull requests unless the maintainers choose a different policy for a specific change.

Delete the branch after merge.
