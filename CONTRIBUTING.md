# Contributing To Gurubodh

Thank you for contributing to Gurubodh. This repository uses an issue-first GitHub workflow with small pull requests and Conventional Commits.

## Start Here

Read these documents before making your first change:

- `README.md` for the repository map and common commands.
- `docs/README.md` for documentation routing.
- `docs/development/github-workflow.md` for the contribution workflow.
- `docs/development/conventional-commits.md` for commit message standards.

## Workflow

1. Select or create a GitHub issue.
2. Create a branch from `main`.
3. Make a scoped change for one issue.
4. Use Conventional Commits.
5. Open a pull request linked to the issue.
6. Run the relevant verification commands.
7. Wait for review and required checks before merge.

## Pull Request Expectations

Pull requests should be small, focused, and linked to one issue.

Include:

- A clear summary.
- The linked issue.
- Verification steps performed.
- Documentation updates, when relevant.
- Any follow-up work that remains.

## Documentation

Update documentation in the same change when setup, architecture, decisions, workflows, schemas, or user-facing behavior changes.

Use:

- `docs/adr/` for architecture decisions.
- `docs/decisions/` for workflow, process, and operational decisions.
- `docs/tasks/` for task briefs and execution history.

## Secrets

Do not commit secrets, credentials, tokens, real `.env` files, private keys, database dumps, or local runtime files.

Use `.env.example` files for documented configuration examples.

## Verification

Use the commands documented in `README.md` and area-specific README files.

If a verification step cannot be run, explain exactly what was skipped and why in the pull request.
