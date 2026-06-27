# Task-005: GitHub integration and Open Source best practices

<record_type>task_history</record_type>
<status>in_progress</status>
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
   - Add GitHub Actions for commit linting and secret scanning.
   - Postpone broader CMS and content-preparation CI until the desired CI strategy is clear.
6. Invite team members after contribution docs exist and `main` is protected.
7. Document semantic versioning expectations now and postpone release automation until release boundaries are clear.

## Execution Results

- Added `docs/decisions/0002-github-contribution-workflow.md` to record the GitHub-native, issue-first workflow.
- Added `docs/development/github-workflow.md` to explain issues, branches, pull requests, review, and merge expectations.
- Added `docs/development/conventional-commits.md` to document commit message and PR title standards.
- Added `CONTRIBUTING.md`, `SECURITY.md`, and `CODE_OF_CONDUCT.md`.
- Added GitHub pull request and issue templates under `.github/`.
- Added a placeholder `.github/CODEOWNERS` file to be filled once GitHub owner or team handles are known.
- Updated `README.md` and `docs/README.md` so the new contributor workflow docs are discoverable.
- Created a project-specific SSH key for GitHub access and configured the local SSH host alias `github.com-gurubodh`.
- Pushed the local repository to GitHub.
- Moved the repository connection to the organization-owned repository `Team-Gurubodh/gurubodh`.
- Confirmed local `origin` points to `git@github.com-gurubodh:Team-Gurubodh/gurubodh.git`.
- Confirmed local `main` tracks `origin/main`.
- Confirmed SSH authentication to GitHub works with the project-specific key.
- Confirmed the `main` branch protection / ruleset is active in the organization repository.
- Created and closed a test issue and pull request to validate the issue-first workflow.
- Invited team members to the GitHub organization / repository as members, with one additional owner assigned.
- Added root Commitlint and Husky configuration for local Conventional Commit enforcement.
- Added a GitHub Actions Commitlint workflow for pull request titles and commits.
- Added a GitHub Actions Gitleaks workflow for secret scanning.
- Documented automation setup in `docs/development/automation.md`.
- Postponed broader CMS and content-preparation CI checks until the team decides the desired CI strategy.
- Confirmed `GITLEAKS_LICENSE` exists as a repository-level GitHub Actions secret.
- Added `Commitlint` and `Gitleaks` as required status checks in the `main` branch ruleset.
- Enabled the ruleset requirement for branches to be up to date before merging.

## Follow-Up

- Replace the placeholder CODEOWNERS entry with actual GitHub users or teams.
- Decide the broader CMS and content-preparation CI strategy in a separate task.
- Decide later whether to add release automation for semantic versioning.
