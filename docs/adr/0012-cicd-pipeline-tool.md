# 0012 — CI/CD Pipeline Tool

## Status

Proposed

## Context

The platform needs automated build, test, and release workflows for the CMS,
future web app, and future backend services across multiple environments.
Specific deployment targets should be decided by the relevant hosting/runtime
ADRs rather than baked into the CI/CD tool decision.

## Decision

**Recommended (pending confirmation):** Use GitHub Actions for CI/CD. Keep the
initial scope focused on repeatable checks, builds, packaging, and controlled
release workflows; add deployment steps once the target runtime for each
component has been decided.

## Consequences

**Positive**
- Tightly integrated with GitHub, assuming source code is hosted there.
- Large marketplace of pre-built actions reduces custom pipeline code.
- No separate CI system to operate or pay for beyond GitHub itself.
- Does not force an early decision about whether each component deploys to ECS,
  Amplify, Lambda, or another AWS runtime.

**Negative**
- More complex multi-account or multi-environment deployment orchestration
  (e.g., approval gates, cross-account IAM roles) requires more manual setup
  than a more "batteries-included" AWS-native option.
- Deployment workflows will still need to be revisited as each component's
  hosting model becomes concrete.

**Alternatives Considered**
- **AWS CodePipeline/CodeBuild** — more native AWS IAM integration for
  cross-account deployments, but lives as a separate system from where the
  code itself is hosted and reviewed.
