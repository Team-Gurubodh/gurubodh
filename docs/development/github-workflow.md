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

Clone the repository with standard GitHub SSH access:

```bash
git clone git@github.com:Team-Gurubodh/gurubodh.git
cd gurubodh
```

If SSH is not available, use HTTPS:

```bash
git clone https://github.com/Team-Gurubodh/gurubodh.git
cd gurubodh
```

Install the toolchain needed for the area you are changing. Common commands are documented in the root `README.md`.

## Issue-First Workflow

Create or select a GitHub issue before starting work. Read its complete description
and available discussion before planning or changing files; the issue defines scope.

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

## Execute Issues With the Slice Workflow

Read and follow the [slice workflow](./slice-workflow.md) before planning or
implementation. It is mandatory for all GitHub issue work until the maintainer
changes or withdraws it. Design review and explicit maintainer acceptance are
mandatory before implementation. Individual review items may become optional
only with approval. Other phases may be brief or marked not applicable with a
reason; scoped exceptions must preserve the workflow's design protections.

Identify the active slice, phase, and intended outcome at session entry. Keep
requirement coverage in the parent issue, establish phase outcomes, and link
verification and reconciliation evidence in a slice-completion record after
each slice. Perform whole-issue review before requesting completion; mark an
issue complete and close it only when the maintainer confirms "implementation
verified" and explicitly instructs completion and closure. At session
exit, post a handoff comment in the parent issue or the slice's sub-issue as
specified by the workflow.

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

Use Conventional Commits and reference the issue in every commit message, as
required by [AGENTS.md](../../AGENTS.md):

```text
<type>(optional-scope): <summary> (#<issue-number>)
```

Examples:

```text
docs(github): add pull request workflow (#12)
ci(commitlint): enforce conventional commit messages (#18)
fix(cms): correct subject relation config (#25)
```

See `docs/development/conventional-commits.md` for details.

## Pull Requests

Open a pull request when the branch is ready for review.

Each pull request should:

- Include the issue reference in its Conventional Commit title, for example
  `docs(github): add pull request workflow (#12)`.
- Link the issue in its description with `Closes #<issue-number>` or `Refs #<issue-number>`.
- Explain the change in plain language.
- List verification performed.
- State whether documentation changed.
- Stay focused on one issue.

Use `Refs` until whole-issue review passes and the maintainer confirms
"implementation verified" and explicitly instructs completion and closure.
Only then may `Closes` be used to close the issue on merge. Verification,
publication, delivery, and closure are separate milestones under the slice workflow.

## Review

Reviewers should check:

- The pull request is linked to one issue.
- The scope is understandable and reviewable.
- Behavior, documentation, and tests match the stated goal.
- Required checks pass.
- The issue contains requirement coverage, slice verification and reconciliation
  evidence, and session handoffs; any workflow exceptions are explicit.
- A closing reference is supported by whole-issue review and explicit maintainer
  verification confirmation and instruction to complete and close the issue.
- No secrets or local-only files are included.

Authors should respond to review comments in the pull request and push follow-up commits to the same branch.

## Merge

Merge only after required checks pass and the required approval has been granted.
Agents must also have explicit maintainer instruction before merging, squashing,
rebasing, or otherwise integrating changes into the target branch; passing checks
and review do not supply that authorization.

Prefer squash merge for small pull requests unless the maintainers choose a different policy for a specific change.

Delete the branch after merge.
