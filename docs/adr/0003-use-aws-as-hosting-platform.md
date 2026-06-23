# 0003 — Use AWS as Hosting Platform

## Status

Accepted

## Context

The platform needs a cloud provider to host the CMS, ingestion/preprocessing
compute, databases, storage, and — in later phases — vector/RAG infrastructure.
Standardizing on a single provider simplifies security model, networking,
billing, and operational knowledge across the team.

## Decision

Use **AWS** as the hosting platform for all infrastructure.

## Consequences

**Positive**
- A single platform to learn and operate, with managed services that map
  directly onto the architecture's needs: ECS/Fargate, RDS, S3, Lambda, Step
  Functions, EventBridge, and Bedrock for the future RAG layer.
- Mature, fine-grained IAM-based security and networking model.
- Broad availability of AWS-experienced engineering talent.

**Negative**
- Heavy use of AWS-specific managed services (e.g., Bedrock, OpenSearch
  Serverless) increases vendor lock-in if a multi-cloud or cloud-portable
  strategy becomes important later.
- Cost management requires discipline — many small managed services can add up
  in ways that are easy to lose track of.
- Requires the team to build and maintain AWS-specific operational knowledge.

**Alternatives Considered**
- **GCP / Azure** — comparable managed-service capability; AWS was chosen based
  on existing team familiarity and account setup.
- **Vercel (for web hosting only)** — excellent Next.js-specific hosting, but
  would still require AWS (or another cloud) for backend services, splitting
  infrastructure across two platforms rather than consolidating on one.
