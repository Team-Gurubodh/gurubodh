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
| [0005 — CI/CD](0005-cicd-pipeline-tool.md) | Proposed broader policy; Actions checks and CLI publication implemented |
| [0006 — R2](0006-use-cloudflare-r2-for-prepared-content-artifacts.md) | Accepted prepared storage; implemented |

Issue [#389](https://github.com/Team-Gurubodh/gurubodh/issues/389) renamed
**ADR-0012: CI/CD Pipeline Tool** to **ADR-0005: CI/CD Pipeline Tool** and
**ADR-0013: Use Cloudflare R2 for Prepared Content Artifacts** to **ADR-0006:
Use Cloudflare R2 for Prepared Content Artifacts**. The
[pinned ADR-0012 source](https://github.com/Team-Gurubodh/gurubodh/blob/9d4a5fd7f8adbb63818c8d1a420cee4e757d1240/docs/adr/0012-cicd-pipeline-tool.md)
and [pinned ADR-0013 source](https://github.com/Team-Gurubodh/gurubodh/blob/9d4a5fd7f8adbb63818c8d1a420cee4e757d1240/docs/adr/0013-use-cloudflare-r2-for-prepared-content-artifacts.md)
preserve the former numbers.

## Open choices

Earlier proposals formerly numbered 0005–0011 are consolidated as topics below;
they are not current numbered records. No separate detailed proposal is required
by the active issue scopes reviewed for #387. Full original proposals are
recoverable in [Git history at the assessed revision](https://github.com/Team-Gurubodh/gurubodh/tree/f9039b13d87ea0bdcf1bb9b746fe4a8f8f788bab/docs/adr).
In particular, current ADR-0005 is distinct from the historical
[ADR-0005: CMS Admin UI Access Control](https://github.com/Team-Gurubodh/gurubodh/blob/f9039b13d87ea0bdcf1bb9b746fe4a8f8f788bab/docs/adr/0005-cms-admin-access-control.md),
and current ADR-0006 is distinct from the historical
[ADR-0006: Content Preparation Orchestration Approach](https://github.com/Team-Gurubodh/gurubodh/blob/f9039b13d87ea0bdcf1bb9b746fe4a8f8f788bab/docs/adr/0006-content-preparation-orchestration.md).
These historical aliases support recovery; they are not active records or number
reservations. All choices below are **Proposed**. Their constraints retain proposal
context and must be reviewed with future implementation; they do not select a
technology.

### CMS admin access

Undecided. The original proposal adds VPN/IP restrictions to Strapi authentication
for mutation-capable administration; editor access friction is the tradeoff.
Choose with actual editor/network requirements.

### Preparation orchestration

Undecided. Native/container batch preparation is implemented. Managed retry,
scheduling, and visibility may justify orchestration; Step Functions was proposed,
not selected. Preserve preparation's artifact handoff and visible failures rather
than introducing CMS writes into preparation.

### Web hosting

Undecided. Amplify was proposed; containers offer more runtime/network control
with greater operational effort. No ECS deployment is established. Choose after
web rendering and operational requirements are known.

### Vector store

Undecided; pgvector was a candidate, not an implementation. Keep retrieval data
rebuildable from CMS content and separate from Strapi-owned tables, roles, and
migrations. Sharing compute may let indexing/query load impair CMS reliability.
Reconsider isolation and store choice against measured retrieval needs. See the
[exploratory RAG task](../tasks/001-RAG-architecture.md).

### Embedding and LLM provider

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

### Mobile framework

Undecided. React Native/Expo was proposed for shared API/types and two-platform
reuse; native customization may add cost. Mobile should reuse CMS/RAG APIs.
Choose when mobile requirements are concrete.

### Infrastructure as code

Undecided. CDK/TypeScript was proposed for toolchain consistency; Terraform offers
portability at the cost of another language. Establish environment reproducibility
and ownership needs before selecting tooling.

## Adding a record

Current local ADRs use a zero-padded contiguous sequence beginning at 0001.
Templates and consolidated open-choice topics are not numbered records. Copy the
[ADR template](../templates/adr-template.md), assign the next number (0007 after
this migration), and update this index. Create an ADR for a boundary, ownership,
dependency, or long-term direction change whose rationale would otherwise be
lost. Mark a replaced record Superseded and link its successor.
