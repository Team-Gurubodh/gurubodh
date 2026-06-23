# 0012 — CI/CD Pipeline Tool

## Status

Proposed

## Context

The platform needs automated build, test, and deploy pipelines for the CMS,
web app, and backend services, across multiple environments.

## Decision

**Recommended (pending confirmation):** Use GitHub Actions for CI/CD —
building container images, pushing them to ECR, and deploying to ECS/Amplify.

## Consequences

**Positive**
- Tightly integrated with GitHub, assuming source code is hosted there.
- Large marketplace of pre-built actions reduces custom pipeline code.
- No separate CI system to operate or pay for beyond GitHub itself.

**Negative**
- More complex multi-account or multi-environment deployment orchestration
  (e.g., approval gates, cross-account IAM roles) requires more manual setup
  than a more "batteries-included" AWS-native option.

**Alternatives Considered**
- **AWS CodePipeline/CodeBuild** — more native AWS IAM integration for
  cross-account deployments, but lives as a separate system from where the
  code itself is hosted and reviewed.
