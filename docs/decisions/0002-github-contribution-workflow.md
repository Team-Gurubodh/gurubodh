# Decision-0002: GitHub Contribution Workflow

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-06-25</date>
<owners>Gurubodh maintainers</owners>

## Context

Gurubodh is moving from a local-only repository to a private GitHub repository so multiple contributors can collaborate before the project is made open source.

The repository needs a simple contribution workflow that new team members can follow without requiring a separate project management system at the start.

## Decision

Use GitHub as the initial collaboration platform for source control, issues, projects, pull requests, and code review.

Prefer SSH for GitHub communication. HTTPS remains the fallback option when SSH cannot be used.

Use GitHub Issues and GitHub Projects as the issue-first workflow. Jira or another external tracker may be considered later if the team outgrows GitHub-native project management.

Protect the `main` branch from the beginning, after the first push creates the branch on GitHub. All normal work should happen through pull requests.

Keep pull requests small and scoped to one issue each. Each pull request should link the issue it resolves or advances.

Use Conventional Commits for commit messages and pull request titles where practical.

## Rationale

- GitHub Issues, Projects, and pull requests keep planning, review, and source history close together.
- Starting with GitHub-native workflows reduces setup cost for the first contributors.
- Branch protection prevents accidental direct changes to `main`.
- Small pull requests reduce review effort and make it easier to understand project history.
- Conventional Commits establish a foundation for future semantic versioning and changelog automation.

## Impact

New contributors should start work from a GitHub issue, create a feature branch, open a scoped pull request, and wait for review before merging.

The repository should include issue templates, a pull request template, contribution guidance, and CI checks that support this workflow.

Release automation can be added later after the repository's release boundaries are better understood.

## Review Trigger

Revisit this decision if the team adopts a dedicated project management tool, changes the default branching model, needs multiple protected long-lived branches, or introduces automated release publishing.
