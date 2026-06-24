# 0008 — Vector Database for RAG (Phase 3)

## Status

Proposed

## Context

Phase 3 requires storing and querying embeddings for semantic retrieval over
CMS content. The architecture treats the RAG layer as derived, not
authoritative: embeddings and vector indexes must always be rebuildable from
CMS content and must not become a second system of record.

The platform already uses PostgreSQL for the CMS, which provides a
low-friction starting point because PostgreSQL can support vector search through
the `pgvector` extension. However, the vector store must remain logically
separate from Strapi-owned tables and must be accessed through the Embedding
Pipeline and RAG Query Service, not by CMS content models.

## Decision

**Recommended (pending confirmation):** Start with the `pgvector` extension on
RDS PostgreSQL for the Phase 3 MVP.

For the earliest MVP, `pgvector` may run on the same RDS PostgreSQL instance as
Strapi only if it is isolated from the CMS schema by separate database/schema
ownership, roles, migrations, and backup/restore expectations. Prefer a
dedicated PostgreSQL database or RDS instance once RAG usage becomes important
enough that vector query load, index tuning, or rebuild operations could affect
CMS reliability.

Revisit Amazon OpenSearch or Bedrock Knowledge Bases if scale, retrieval
features, operational needs, or managed RAG workflow support grow beyond what
pgvector comfortably handles.

## Consequences

**Positive**
- No new database technology to operate at MVP stage — reuses PostgreSQL
  operational knowledge and tooling.
- Lower cost than a dedicated vector engine for moderate content volumes.
- Keeps the RAG layer rebuildable and derived when paired with clear ownership
  boundaries and rebuild procedures.

**Negative**
- `pgvector`'s similarity-search performance and feature set are more limited
  than purpose-built vector engines at large scale.
- May require a migration later if content volume or query load grows
  significantly.
- Sharing infrastructure with the CMS can create reliability risk if vector
  indexing, rebuilds, or query load compete with CMS traffic; this must be
  managed through isolation or a dedicated database/runtime.

**Alternatives Considered**
- **Amazon OpenSearch Service/Serverless (vector engine)** — scales better for
  large datasets, but is a new managed service to operate.
- **Amazon Bedrock Knowledge Bases** — least custom code, since chunking,
  embedding, and retrieval are managed for you, but ties the system to
  Bedrock's managed behavior with less flexibility over the pipeline.
- **Standalone vector DB (e.g., Pinecone)** — not AWS-native, which adds a
  separate vendor relationship and contradicts the AWS-centric hosting
  decision (ADR-0003).
