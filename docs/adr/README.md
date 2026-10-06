# Architectural Decision Records

<record_collection>architecture_decisions</record_collection>

ADRs own consequential rationale, tradeoffs, and reconsideration triggers.
The [architecture overview](../architecture.md) owns the system map; interface
contracts and code own semantics and implementation details.

## Status legend

- **Accepted** — explicitly decided for the stated scope; does not prove implementation or deployment.
- **Proposed** — undecided; a recommendation grants no acceptance or implementation authorization.
- **Superseded** — replaced by an identified later record; consult its replacement for current scope.

These meanings also apply to [operational decisions](../decisions/README.md).

## Records

| Record | Status and scope |
| --- | --- |
| [0001 — Strapi](0001-use-strapi-as-headless-cms.md) | Accepted CMS choice; implemented |
| [0002 — Next.js](0002-use-nextjs-for-web-frontend.md) | Accepted web framework; unimplemented |
| [0003 — AWS](0003-use-aws-as-hosting-platform.md) | Accepted hosting direction, qualified by R2; no deployment claim |
| [0004 — API style](0004-strapi-api-style.md) | Proposed broader policy; REST seed writes implemented |
| [0012 — CI/CD](0012-cicd-pipeline-tool.md) | Proposed broader policy; Actions checks and CLI publication implemented |
| [0013 — R2](0013-use-cloudflare-r2-for-prepared-content-artifacts.md) | Accepted prepared storage; implemented |

## Open choices

ADRs 0005–0011 are consolidated below. No separate detailed proposal is required
by the active issue scopes reviewed for #387. Numbers remain reserved; full original
proposals are recoverable in [Git history at the assessed revision](https://github.com/Team-Gurubodh/gurubodh/tree/f9039b13d87ea0bdcf1bb9b746fe4a8f8f788bab/docs/adr).
All choices here are **Proposed**. Constraints below retain proposal context and
must be reviewed with the future implementation; they do not select a technology.

### ADR-0005 — CMS admin access

Undecided. The original proposal adds VPN/IP restrictions to Strapi authentication
for mutation-capable administration; editor access friction is the tradeoff.
Choose with actual editor/network requirements.

### ADR-0006 — Preparation orchestration

Undecided. Native/container batch preparation is implemented. Managed retry,
scheduling, and visibility may justify orchestration; Step Functions was proposed,
not selected. Preserve preparation's artifact handoff and visible failures rather
than introducing CMS writes into preparation.

### ADR-0007 — Web hosting

Undecided. Amplify was proposed; containers offer more runtime/network control
with greater operational effort. No ECS deployment is established. Choose after
web rendering and operational requirements are known.

### ADR-0008 — Vector store

Undecided; pgvector was a candidate, not an implementation. Keep retrieval data
rebuildable from CMS content and separate from Strapi-owned tables, roles, and
migrations. Sharing compute may let indexing/query load impair CMS reliability.
Reconsider isolation and store choice against measured retrieval needs. See the
[exploratory RAG task](../tasks/001-RAG-architecture.md).

### ADR-0009 — Embedding and LLM provider

Undecided. Bedrock/Titan/Claude were proposed. Local BGE-M3 chunk-boundary
experiments do not select a production retrieval provider. Evaluate Hindi/Marathi
and domain-specific retrieval/answer quality before choosing.

Retain the comparability constraint: provider/model, mode, dimensions,
normalization, index/chunking versions, and source/chunk identity must identify
which vectors can be compared. Model-dependent calls belong behind a provider
boundary. Changing model, mode, dimensions, or normalization requires embedding
regeneration and affected-index rebuild, not canonical content replacement.
Dense-first retrieval was a simplification proposal; sparse/multi-vector support
needs separate design. See the [RAG task](../tasks/001-RAG-architecture.md).

### ADR-0010 — Mobile framework

Undecided. React Native/Expo was proposed for shared API/types and two-platform
reuse; native customization may add cost. Mobile should reuse CMS/RAG APIs.
Choose when mobile requirements are concrete.

### ADR-0011 — Infrastructure as code

Undecided. CDK/TypeScript was proposed for toolchain consistency; Terraform offers
portability at the cost of another language. Establish environment reproducibility
and ownership needs before selecting tooling.

## Adding a record

Use the [ADR template](0000-template.md), choose an unused sequential number,
and update this index. Create an ADR for a boundary, ownership, dependency, or
long-term direction change whose rationale would otherwise be lost. Mark a
replaced record Superseded and link its successor. The
[template entry point](../templates/adr-template.md) routes to the same template.
