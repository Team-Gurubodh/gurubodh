# 0001 — Use Strapi as Headless CMS

## Status

Accepted

## Context

The platform needs a headless CMS to store structured content and metadata,
support content modeling (types, relations, taxonomies), manage a publishing
lifecycle, and expose that content via API to ingestion/preprocessing tools
(writes) and the web/mobile consumption layers (reads). We want to avoid
recurring SaaS costs and vendor lock-in tied to a proprietary content store,
and we are comfortable taking on the operational responsibility of hosting it
ourselves.

## Decision

Adopt **Strapi**, self-hosted, as the headless CMS.

## Consequences

**Positive**
- Full control over hosting, scaling, and data residency — no third-party
  vendor holds our content.
- No per-seat or usage-based SaaS pricing as content volume or editor count grows.
- Customizable via plugins and custom content types; supports both REST and
  GraphQL out of the box.
- Large open-source ecosystem, including an S3 upload provider that fits an
  AWS-based deployment.

**Negative**
- We own the full operational burden: hosting, scaling, database management,
  upgrades, and security patching — none of this is offloaded to a vendor.
- Strapi's content modeling and plugin maturity can lag behind some commercial
  competitors for very large-scale or complex localization scenarios.
- Self-hosting requires us to also operate a database (PostgreSQL) and compute
  layer, which is additional infrastructure to maintain.

**Alternatives Considered**
- **Contentful (SaaS)** — less operational burden, but recurring cost that
  scales with usage and a degree of vendor lock-in.
- **Sanity (SaaS)** — strong structured-content tooling, but a proprietary
  query language (GROQ) increases lock-in.
- **Custom-built CMS** — maximum control, but high build cost and re-solving
  problems (admin UI, permissions, media handling) that existing tools already
  solve well.
