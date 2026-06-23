# 0007 — Next.js Hosting Model on AWS

## Status

Proposed

## Context

Next.js needs a hosting model on AWS that supports the rendering modes (SSG,
ISR, SSR) the web consumption layer relies on for a content-heavy site.

## Decision

**Recommended (pending confirmation):** Use AWS Amplify Hosting, which provides
first-class managed support for Next.js SSR/ISR. Revisit ECS Fargate if more
control over the runtime or networking is needed later.

## Consequences

**Positive**
- Amplify Hosting manages Next.js-specific build and runtime concerns (ISR
  revalidation, image optimization, etc.) with less custom operational work
  than self-managing these on ECS.

**Negative**
- Less control over the underlying runtime and networking compared to ECS.
- Introduces another AWS managed service with its own pricing model and limits
  to learn, alongside the ECS-based services used elsewhere.

**Alternatives Considered**
- **ECS Fargate + ALB** — consistent with how the rest of the stack (CMS,
  services) is hosted, and gives full control, but requires manually
  replicating Next.js-specific features such as ISR on-demand revalidation.
