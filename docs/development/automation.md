# Automation

<record_type>workflow_guide</record_type>
<status>active</status>

This guide documents repository automation that supports the GitHub contribution workflow.

## Current Automation

The repository currently has automation for:

- Conventional Commit enforcement.
- Secret scanning.
- CLI tests, distribution-resource validation, installed-runtime checks, and
  container publication.

The CLI workflow is scoped to `tools/gurubodh-cli`; it is not CMS or full-monorepo
CI. Broader coverage for other project areas remains undecided.

## Local Commit Linting

Commitlint and Husky run locally through the `commit-msg` hook.

Install root governance tooling from the monorepo root:

```bash
npm ci
```

The root governance tooling expects Node.js `>=22.12.0 <=26.x.x` and npm `>=10.0.0`.

Husky is installed by the root `prepare` script. New commits are checked against the Conventional Commits configuration in `commitlint.config.cjs`.

To manually check commits on the current branch against `origin/main`:

```bash
npm run commitlint
```

## GitHub Commit Linting

The `Commitlint` workflow checks pull requests by validating:

- The pull request title.
- The commits included in the pull request.

Use a Conventional Commit pull request title with an issue reference, as required
by [AGENTS.md](../../AGENTS.md), especially when squash merging.

Example:

```text
docs(github): add issue-first workflow (#25)
```

## Secret Scanning

The `Secret Scan` workflow uses Gitleaks to scan pull requests, scheduled weekly runs, and manual workflow runs.

Because Gurubodh is owned by a GitHub organization, `gitleaks/gitleaks-action` requires a `GITLEAKS_LICENSE` repository or organization secret.

Add the secret in GitHub:

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

Secret name:

```text
GITLEAKS_LICENSE
```

The action also uses GitHub's automatic `GITHUB_TOKEN`.

## CLI Validation And Container Publication

The [gurubodh-cli container workflow](../../.github/workflows/gurubodh-cli-container.yml)
runs on:

- Pull requests affecting `tools/gurubodh-cli/**` or the workflow file itself.
- Pushes to `main` affecting those same paths.
- Pushes of tags matching `cli-v*`; path filters do not restrict tag pushes.

It validates runtime resources in source distributions and wheels, and builds
and tests container images on both `linux/amd64` and `linux/arm64`. Checks cover
the CLI unit suite, CLI and bundled Node runtime, installed component contracts
and resource discovery, offline command execution, composition inspection, and
all 26 maintained selectors.

Publication runs only on push events, after distribution validation and both
architecture test jobs pass. It publishes the tested images to
`ghcr.io/team-gurubodh/gurubodh-cli` with commit-SHA tags and, for release-tag
pushes, the matching `cli-v*` tag. Pull requests validate without publishing.
See the [production image and installed-runtime guide](../../tools/gurubodh-cli/docs/operations/r2-production-runs.md#automated-image-verification)
for the runtime boundary and local reproduction commands.

## Branch Protection

Workflow definitions show which checks run; they do not establish which checks
are required by branch protection. Inspect the current `main` ruleset in GitHub
for required checks and review requirements. The workflow files alone do not
verify that `Commitlint`, `Gitleaks`, or any CLI job is a required check.
