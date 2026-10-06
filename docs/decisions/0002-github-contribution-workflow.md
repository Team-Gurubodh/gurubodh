# Decision-0002: GitHub Contribution Workflow

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-06-25</date>
<owners>Gurubodh maintainers</owners>

## Decision and rationale

Use GitHub for source, issues, PRs, and review. Keeping scope and review near
source history avoids introducing a separate tracker for the initial team.
Dedicated branches and scoped PRs make changes reviewable; Conventional Commits
provide a basis for future release automation.

Current mechanics belong to [GitHub conventions](../development/github-workflow.md),
and lifecycle/authorization belongs to the [slice workflow](../development/slice-workflow.md).
[#357](https://github.com/Team-Gurubodh/gurubodh/issues/357) made Projects optional,
replacing the original mandatory tracking direction.

## Review trigger

Reconsider when a dedicated tracker, different branching model, or automated
release process becomes necessary. Historical setup instructions remain in Git.
