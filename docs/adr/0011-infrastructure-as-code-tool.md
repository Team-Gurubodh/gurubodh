# 0011 — Infrastructure as Code Tool

## Status

Proposed

## Context

AWS infrastructure (ECS, RDS, S3, networking, and more) needs to be defined as
code so it is reproducible across dev, staging, and production environments.

## Decision

**Recommended (pending confirmation):** Use AWS CDK (TypeScript) so
infrastructure code shares a language and toolchain with the application
codebase.

## Consequences

**Positive**
- Using TypeScript across both application and infrastructure code reduces
  context-switching for the team.
- CDK constructs map closely to AWS services, making infrastructure intent
  easier to express and read than raw CloudFormation templates.

**Negative**
- CDK is AWS-specific and not portable to other cloud providers.
- The team needs to learn CDK's abstraction layer in addition to understanding
  the underlying AWS resources it generates.

**Alternatives Considered**
- **Terraform** — multi-cloud portable with a large community and module
  ecosystem, but uses HCL, a separate language from the rest of the stack.
