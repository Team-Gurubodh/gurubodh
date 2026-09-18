# Conventional Commits

<record_type>workflow_guide</record_type>
<status>active</status>

Gurubodh uses Conventional Commits to make history readable and to prepare for future semantic versioning and changelog automation.

## Format

```text
<type>(optional-scope): <summary> (#<issue-number>)
```

The summary should be short, imperative, and lowercase unless it contains a proper noun.

Commit messages and pull request titles must reference the issue under
[AGENTS.md](../../AGENTS.md). The examples use illustrative issue numbers; use the
issue that owns your change. In the PR description, use `Refs #<issue-number>`
for partial delivery and `Closes #<issue-number>` only for completed issues.

## Common Types

- `feat` - user-facing feature or meaningful capability.
- `fix` - bug fix.
- `docs` - documentation-only change.
- `chore` - maintenance task that does not affect behavior.
- `refactor` - code change that preserves behavior.
- `test` - test-only change.
- `build` - dependency, packaging, or build-system change.
- `ci` - CI or automation change.
- `perf` - performance improvement.

## Scopes

Use scopes when they help readers understand the affected area.

Recommended scopes include:

- `cms`
- `content`
- `database`
- `docs`
- `github`
- `ci`
- `agents`

## Examples

```text
docs(github): add issue-first workflow (#25)
ci(commitlint): validate pull request titles (#18)
feat(content): add metadata validation command (#26)
fix(cms): correct category route config (#27)
chore(deps): update strapi dependencies (#28)
```

## Breaking Changes

Use `!` when a commit introduces a breaking change:

```text
feat(cms)!: rename public subject identifier (#29)
```

Include details in the commit body:

```text
BREAKING CHANGE: subject consumers must use the new public identifier field.
```

## Semantic Versioning

When release automation is introduced, the default version impact should be:

- `fix` creates a patch release.
- `feat` creates a minor release.
- Commits marked with `!` or `BREAKING CHANGE:` create a major release.
- `docs`, `chore`, `ci`, `test`, `build`, and `refactor` do not normally create releases.
