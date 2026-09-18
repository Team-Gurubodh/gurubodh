# Architectural Decision Records

<record_collection>architecture_decisions</record_collection>

Use this directory for durable architectural decisions that affect system boundaries, data ownership, runtime dependencies, deployment shape, or long-term technical direction.

Each ADR captures a single decision, the context that motivated it, and its consequences (including tradeoffs and alternatives considered). Use the [authoritative ADR template](./0000-template.md) for its structure and metadata.

The companion [architecture.md](../architecture.md) describes the stable component structure these decisions implement. ADRs explain *why*; the architecture overview explains *what* and *how things fit together*.

## Status Legend

- **Accepted** — decided and in effect.
- **Proposed** — not yet decided; a recommended default is recorded so work can
  proceed, but it should be revisited and confirmed (status updated to
  Accepted) before being treated as final.
- **Superseded** — replaced by a later ADR (the later ADR is linked).

## Index

| # | Title | Status |
|---|---|---|
| [0001](./0001-use-strapi-as-headless-cms.md) | Use Strapi as Headless CMS | Accepted |
| [0002](./0002-use-nextjs-for-web-frontend.md) | Use Next.js for Web Frontend | Accepted |
| [0003](./0003-use-aws-as-hosting-platform.md) | Use AWS as Hosting Platform | Accepted |
| [0004](./0004-strapi-api-style.md) | Strapi API Style: REST vs GraphQL | Proposed |
| [0005](./0005-cms-admin-access-control.md) | CMS Admin UI Access Control | Proposed |
| [0006](./0006-content-preparation-orchestration.md) | Content Preparation Orchestration Approach | Proposed |
| [0007](./0007-nextjs-hosting-model-on-aws.md) | Next.js Hosting Model on AWS | Proposed |
| [0008](./0008-vector-database-for-rag.md) | Vector Database for RAG (Phase 3) | Proposed |
| [0009](./0009-embedding-model-and-llm-provider.md) | Embedding Model and LLM Provider (Phase 3) | Proposed |
| [0010](./0010-mobile-app-framework.md) | Mobile App Framework (Phase 4) | Proposed |
| [0011](./0011-infrastructure-as-code-tool.md) | Infrastructure as Code Tool | Proposed |
| [0012](./0012-cicd-pipeline-tool.md) | CI/CD Pipeline Tool | Proposed |
| [0013](./0013-use-cloudflare-r2-for-prepared-content-artifacts.md) | Use Cloudflare R2 for Prepared Content Artifacts | Accepted |


## Adding a New ADR

1. Copy the [authoritative ADR template](./0000-template.md) and choose the next sequential number.
2. Use the format: `NNNN-short-kebab-case-title.md`.
3. Fill in the template's metadata and sections.
4. Add a row to the Index table above.
5. If an ADR replaces an earlier one, mark the old one **Superseded** and link
   forward to the new ADR.

The existing [templates/adr-template.md](../templates/adr-template.md) entry point links to the same authoritative template.


## When To Create An ADR

- A decision changes architecture boundaries.
- A decision affects multiple applications, tools, or environments.
- A decision is expensive to reverse.
- Future agents or maintainers will need to know why the choice was made.
