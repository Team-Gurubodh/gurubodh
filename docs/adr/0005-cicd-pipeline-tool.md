# 0005 — CI/CD Pipeline Tool

## Status

Proposed — broader deployment policy remains undecided.

## Current evidence and open decision

[GitHub Actions workflows](../../.github/workflows/) implement commit/title checks,
secret scanning, and CLI distribution/container verification and GHCR publication.
[Container rationale](../decisions/0004-gurubodh-cli-container-publication-and-runtime.md)
records the accepted bounded runtime choice. These implementations do not establish
CMS/web deployment targets or a repository-wide continuous-deployment policy.

The original proposal favors GitHub Actions to keep checks and source review
in one platform without operating a separate CI system. Multi-account/environment
deployment still needs target-specific security and approval design. Reconsider
when deployment requirements exceed these maintained workflows.
