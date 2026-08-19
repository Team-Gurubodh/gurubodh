# Decision-0004: Gurubodh CLI Container Publication and Runtime

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-08-19</date>
<owners>Gurubodh maintainers</owners>

## Context

The CLI needs a reproducible operational runner for R2-backed content-preparation
jobs without replacing native Python development workflows.

## Decision

- Publish the CPU-only CLI image as `ghcr.io/team-gurubodh/gurubodh-cli`.
- Support `linux/amd64` and `linux/arm64`. Intel Macs pull amd64; Apple Silicon
  Macs pull arm64.
- Each invocation is one bounded batch job and exits. Production flow is R2 input
  to a temporary container workspace to R2 output.
- Images are tagged immutably as `sha-<full-git-sha>`. A human-readable
  `cli-v*` Git tag publishes an additional matching release tag; neither policy
  permits moving a SHA tag. Pull by digest for the strongest deployment pin.
- The package is linked to this repository and follows its visibility. Maintainers
  manage package access in GHCR and grant pull access only to required users or
  teams before production use.
- GitHub Actions uses `contents: read` and grants `packages: write` only to the
  publish job. `GITHUB_TOKEN` publishes images; Cloudflare credentials are never
  present in CI or image layers.
- OCI labels record source URL, source revision, version, and creation time.
  The build also writes equivalent non-secret provenance into the image for audit
  reports. Production commands run baked-in code and must not bind-mount a mutable
  checkout over `/opt/gurubodh-cli`.
- `/opt/gurubodh-cli` is the project root, `/work` is the writable temporary
  workspace, and `/var/cache/gurubodh/models` is the persistent model-cache
  mount point. The image runs as a non-root `gurubodh` user.

## Rationale

This keeps credentials and content outside the image while making source identity
available after the repository metadata has been excluded from the runtime image.

## Impact

Native Python execution remains the supported development and debugging path.
Docker Compose, GPU images, scheduling, workers, and atomic/versioned R2
publication remain out of scope.

## Review Trigger

Review on a registry/access-policy change, a GPU runtime requirement, or an
orchestrated job model.
