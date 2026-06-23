# 0009 — Embedding Model and LLM Provider (Phase 3)

## Status

Proposed

## Context

The RAG layer needs an embedding model to vectorize content and queries, and
an LLM to generate grounded answers from retrieved content.

## Decision

**Recommended (pending confirmation):** Use Amazon Bedrock for both — Titan
Embeddings for vectorization and a Claude model for answer generation — to
keep the RAG stack AWS-native and consistent with the platform's overall
hosting decision (ADR-0003).

## Consequences

**Positive**
- A single AWS bill and IAM model governs access to both the embedding model
  and the LLM, rather than managing a separate vendor relationship and API key.
- Data stays within the AWS account boundary already used for the rest of the
  platform.

**Negative**
- Tied to whichever models Bedrock offers and supports, which may lag behind
  using a provider's API directly.
- Switching embedding models later requires re-embedding all existing content,
  so this choice has real switching costs once content volume grows.

**Alternatives Considered**
- **OpenAI or Cohere APIs directly** — potentially best-in-class models for
  embeddings or generation, but introduces a non-AWS vendor with separate
  billing, security review, and data-handling considerations.
