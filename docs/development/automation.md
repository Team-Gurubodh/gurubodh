# Automation

<record_type>workflow_guide</record_type>
<status>active</status>

This guide documents repository automation that supports the GitHub contribution workflow.

## Current Automation

The repository currently has automation for:

- Conventional Commit enforcement.
- Secret scanning.

Broader CI for the CMS, content-preparation tools, and other project areas is intentionally postponed until the team decides which checks should run and when.

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

Use a Conventional Commit pull request title, especially when squash merging.

Example:

```text
docs(github): add issue-first workflow
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

## Branch Protection

After the workflows have run successfully at least once, add these required checks to the `main` ruleset:

- `Commitlint`
- `Gitleaks`

Do not add broader CI checks until the team decides the project-level CI strategy.
