# Task-005: GitHub integration and Open Source best practices

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-06-25</date>
<owners>Gurubodh maintainers</owners>

## Goal

- Establish local repo controls and create supporting documentation to make the repo ready to be open-sourced at a later date.
- We need to have a private repo on GitHub where other team members can contribute. But before that I need to push the present git repo to GitHub.
- We need to add branch protection within the GitHub repo to prevent direct pushes to `main`.
- We need to have templates / standards in place, together with documentation, within the local git repo that sets the stage for `pull requests`, `Conventional Commits`.
- We need to have process and automation in place, together with documentation, within the local git repo that sets the stage for `commit linting`, `semantic versioning` using tools like Commitlint with Husky or equivalent.
- Create a new ssh key especially for this project.

## Context
- I have a `gurubodh` repo ready in GitHub that is not initialized. So my push will be the first one on GitHub.
- Four more team members will begin to contribute to this project soon.
- I wish to establish good standards and best practices from the beginning such as pull request, conventional commits and semantic versioning
- Project documentation should be updated so that even a newcomer can get started with GitHub following these instructions.

## Decisions
- Communication with GitHub should be over `SSH` with `HTTPS` being the fallback option.
- I would like to have branch protection on `main` from the beginning.
- I would like to have Issue-first workflow with GitHub issues and projects rather than Jira integration to begin with. This will keep the learning curve manageable.
- I would like to keep PRs small and scoped to one issue each.

## Approved Plan

1. Establish local repository standards before the first GitHub push.
   - Add a durable GitHub contribution workflow decision under `docs/decisions/`.
   - Add contributor-facing documentation for GitHub workflow and Conventional Commits.
   - Add root contributor, security, and conduct documents.
   - Add GitHub issue templates, a pull request template, and a placeholder CODEOWNERS file.
2. Create a project-specific SSH key for GitHub access.
   - Prefer SSH for normal GitHub communication.
   - Use HTTPS only as a fallback.
3. Push the existing local repository to the empty private GitHub repository.
   - Create the remote `main` branch with the first push.
4. Configure branch protection or a repository ruleset for `main` immediately after the first push.
   - Require pull requests before merge.
   - Require at least one approval at the start.
   - Block force pushes and branch deletion.
   - Require conversation resolution and required checks once automation is available.
5. Add automation in a follow-up scoped change.
   - Add Commitlint and Husky for local Conventional Commit enforcement.
   - Add GitHub Actions for commit linting, CI checks, and secret scanning.
6. Invite team members after contribution docs exist and `main` is protected.
7. Document semantic versioning now and add release automation later when release boundaries are clear.

## Execution Results

- Added `docs/decisions/0002-github-contribution-workflow.md` to record the GitHub-native, issue-first workflow.
- Added `docs/development/github-workflow.md` to explain issues, branches, pull requests, review, and merge expectations.
- Added `docs/development/conventional-commits.md` to document commit message and PR title standards.
- Added `CONTRIBUTING.md`, `SECURITY.md`, and `CODE_OF_CONDUCT.md`.
- Added GitHub pull request and issue templates under `.github/`.
- Added a placeholder `.github/CODEOWNERS` file to be filled once GitHub owner or team handles are known.
- Updated `README.md` and `docs/README.md` so the new contributor workflow docs are discoverable.

## Follow-Up

- Create the project-specific SSH key and add it to GitHub.
- Push the repository to the empty private GitHub repository.
- Configure `main` branch protection immediately after the first push.
- Add Commitlint, Husky, GitHub Actions CI, and secret scanning in a separate scoped change.
- Replace the placeholder CODEOWNERS entry with actual GitHub users or teams.
