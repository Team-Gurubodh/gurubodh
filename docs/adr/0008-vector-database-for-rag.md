# 0008 — Vector Database for RAG (Phase 3)

## Status

Proposed

## Context

Phase 3 requires storing and querying embeddings for semantic retrieval over
CMS content. The platform already operates an RDS PostgreSQL instance for
Strapi, which provides a low-friction starting point if it can also serve
vector search needs.

## Decision

**Recommended (pending confirmation):** Start with the `pgvector` extension on
RDS PostgreSQL (the existing instance or a dedicated one) for the Phase 3 MVP.
Revisit Amazon OpenSearch or Bedrock Knowledge Bases if scale or feature needs
grow beyond what pgvector comfortably handles.

## Consequences

**Positive**
- No new database technology to operate at MVP stage — reuses existing RDS
  operational knowledge, backup strategy, and tooling.
- Lower cost than a dedicated vector engine for moderate content volumes.

**Negative**
- `pgvector`'s similarity-search performance and feature set are more limited
  than purpose-built vector engines at large scale.
- May require a migration later if content volume or query load grows
  significantly.

**Alternatives Considered**
- **Amazon OpenSearch Service/Serverless (vector engine)** — scales better for
  large datasets, but is a new managed service to operate.
- **Amazon Bedrock Knowledge Bases** — least custom code, since chunking,
  embedding, and retrieval are managed for you, but ties the system to
  Bedrock's managed behavior with less flexibility over the pipeline.
- **Standalone vector DB (e.g., Pinecone)** — not AWS-native, which adds a
  separate vendor relationship and contradicts the AWS-centric hosting
  decision (ADR-0003).
