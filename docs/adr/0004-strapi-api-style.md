# 0004 — Strapi API Style: REST vs GraphQL

## Status

Proposed

## Context

Strapi supports both a REST API and a GraphQL plugin. Content Ingestion and
Metadata Ingestion need to write data into the CMS; the web (and later mobile)
consumption layers need to read it. Content Preparation and Metadata Generation
produce artifacts, but do not write finalized content or metadata directly into
the CMS. Treating both API styles as "canonical" doubles the contract surface
that has to be tested, documented, and kept stable.

## Decision

**Recommended (pending confirmation):** Use REST as the canonical API for
server-to-server writes from Content Ingestion and Metadata Ingestion. Treat
GraphQL as optional for the web UI's read side, to be added only if/when query
flexibility (e.g., fetching deeply nested relations in a single call) becomes a
genuine pain point.

## Consequences

**Positive**
- Keeps write-side tooling simple: REST is easy to log, debug, and build
  idempotency checks around in ingestion scripts that may be written in varied
  languages.
- Avoids running two parallel API surfaces from day one.

**Negative**
- If the web UI later needs GraphQL for complex nested queries, adding it
  means introducing and maintaining a second API surface and schema.

**Alternatives Considered**
- **GraphQL-only** — powerful querying for the read side, but adds schema
  design overhead, N+1 query risk, and is a less common pattern for the kind of
  simple server-to-server write operations ingestion tooling performs.
