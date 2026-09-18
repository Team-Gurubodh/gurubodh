# Contributing To Gurubodh

Thank you for contributing to Gurubodh. This repository uses an issue-first GitHub workflow with small pull requests and Conventional Commits.

## Start Here

Read these documents before making your first change:

- `README.md` for the repository map and common commands.
- `docs/README.md` for documentation routing.
- `docs/development/github-workflow.md` for the contribution workflow.
- `docs/development/slice-workflow.md` for the mandatory issue execution workflow.
- `docs/development/git-github-cli-workflow-tutorial.md` for a beginner-friendly Git and GitHub CLI walkthrough.
- `docs/development/conventional-commits.md` for commit message standards.

## Workflow

1. Select or create a GitHub issue.
2. Choose the issue template that matches the work type: Feature, Bug Report, Documentation, Decision, or Task.
3. Create a branch from `main`.
4. Follow the [slice workflow](docs/development/slice-workflow.md): map requirements, identify the active slice and phase, establish phase outcomes, implement, verify, and reconcile evidence.
5. Use Conventional Commits.
6. Open a pull request linked to the issue.
7. Run the relevant verification commands.
8. Wait for review and required checks before merge.

The slice workflow is mandatory for all GitHub issue work until the maintainer
changes or withdraws it. Read it before planning or implementation. At session
entry, state the active slice, phase, and intended outcome; at exit, post a
handoff comment in the relevant issue. Design review and explicit maintainer
acceptance are mandatory before implementation. Obtain approval before making
individual design-review items optional. Other phases may be brief or marked
not applicable with a reason. Scoped exceptions must preserve these design
protections and be recorded in the issue.

## Pull Request Expectations

Pull requests should be small, focused, and linked to one issue.

Include:

- A clear summary.
- The linked issue.
- Verification steps performed.
- Documentation updates, when relevant.
- Any follow-up work that remains.
- Links to slice verification and reconciliation evidence in the issue; complete
  the whole-issue review before requesting completion. Use a closing reference
  only after the maintainer confirms "implementation verified" and explicitly
  instructs completion and closure; otherwise use `Refs #<issue-number>`.

## Documentation

Update documentation in the same change when setup, architecture, decisions, workflows, schemas, or user-facing behavior changes.

Use:

- `docs/adr/` for architecture decisions.
- `docs/decisions/` for workflow, process, and operational decisions.
- GitHub issues for current slice tracking, execution evidence, and session handoff comments.

## Secrets

Do not commit secrets, credentials, tokens, real `.env` files, private keys, database dumps, or local runtime files.

Use `.env.example` files for documented configuration examples.

## Verification

Use the commands documented in `README.md` and area-specific README files.

If a verification step cannot be run, explain exactly what was skipped and why in the pull request.
