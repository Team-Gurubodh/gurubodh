# Architecture Overview

<record_type>architecture_overview</record_type>
<status>living</status>

## 1. Purpose & Scope

This overview describes current components and their planned connections.
Implementation labels below describe the checked-in system; accepted
[ADRs](adr/README.md) explain choices but do not establish deployment status.
Component guides and linked contracts own detailed procedures and fields.

---

## 2. Architectural Principles

These principles hold regardless of which specific technology implements a
component, and should guide future decisions:

1. **The CMS is the single source of truth for content and metadata.** No other
   component stores published content state; everything else either feeds the
   CMS or reads from it.
2. **Preparation and ingestion are decoupled from each other and from the CMS.**
   Each stage hands off through a staging boundary so that a failure or slowdown
   in one stage does not corrupt or block another.
3. **Consumption layers (web, chat, mobile) are stateless clients of the
   CMS/RAG APIs.** They never write to the CMS directly and never talk to
   preparation or ingestion directly.
4. **The RAG layer is derived, not authoritative.** Embeddings and vector data are
   always rebuildable from CMS content; the vector store is never a system of
   record.
5. **New consumption channels reuse existing APIs.** Chat and mobile are
   expected to consume the same CMS/RAG APIs as web, not channel-specific
   backends.

---

## 3. System Context

Solid arrows show implemented handoffs; dotted arrows and **Planned** labels
show future work. “Implemented” means supported by the repository, not that a
service is deployed. AWS hosting remains a direction, not a deployment claim.

```mermaid
flowchart LR
    CSV["External seed-data CSVs"] --> SEED["Implemented: seed-data CLI"]
    SEED --> JSON["Validated JSON artifacts"]
    JSON --> API["Implemented: Strapi API seed ingestion<br/>Categories, Subjects, both glossaries"]
    API --> CMS["Implemented: Strapi + PostgreSQL<br/>Published content and metadata"]
    DOCX["Source DOCX"] --> PREP["Implemented: content preparation"]
    PREP --> STORE["Implemented: local / Cloudflare R2 artifacts<br/>Canonical chapter text, metadata, provenance"]
    STORE --> DERIVED["Implemented: derived semantic chunks<br/>and DOCX exports"]
    STORE -.-> ING["Planned: chapter-content ingestion"]
    ING -.-> CMS
    STORE -.-> META["Planned: metadata generation + ingestion"]
    META -.-> CMS
    CMS -.-> CLIENT["Planned: web, chat, mobile"]
    CMS -.-> RAG["Planned: embeddings, vector store, RAG service"]
    RAG -.-> CLIENT
    CMS -.-> MEDIA["Planned: CMS cloud media storage"]
```

[Seed artifacts](interfaces/seed-data-artifacts.md) reach the CMS today.
[Prepared artifacts](interfaces/prepared-content-artifacts.md) have their own
local/R2 storage boundary; chapter ingestion into the CMS is missing. Prepared
chunks are derived files, not a deployed retrieval service. R2 prepared storage
is separate from both PostgreSQL and the planned CMS media provider.

### Domain vocabulary

A **Category** groups **Subjects**; each Subject references one Category.
A subject's source DOCX commonly contains several lectures. Preparation splits
it at editorial chapter headings into **Chapters**. The repository uses
**Prabodhan** for these numbered divisions in
[DOCX export titles](interfaces/prepared-content-artifacts.md#derived-docx-exports)
and stores an optional subject-level `prabodhan_count`; this does not establish
that every audio lecture, chapter, and source file has a one-to-one identity.
A **Chunk** is a generated semantic segment of prepared chapter text, not an
editorial chapter. Chapter and Chunk CMS collections are not implemented.

Hindi (`hi-IN`) and Marathi (`mr-IN`) are separate prepared editions of a
subject, with independent release roots, provenance, checkpoints, and derived
outputs; see [locale scope](decisions/0005-language-scoped-prepared-content-release-roots.md).
This is distinct from Category/Subject CMS display localizations: seed ingestion
writes English (`en`) and Hindi (`hi-IN`). It does not ingest Marathi chapters.

**Sanatan Glossary** and **Prabodhan Glossary** hold separately maintained term
and definition reference data, intended to support future tagging/content
descriptors. Today they are independent, non-localized collections with no
chapter relationships or automatic tagging. Their [shared contract](interfaces/seed-data-artifacts.md#glossary-strapi-collection-type-contract)
does not define an editorial rule for assigning a term to one versus the other;
the maintainer explicitly left that narrow distinction open under
[#353](https://github.com/Team-Gurubodh/gurubodh/issues/353).

| Identifier | What it identifies and whether text edits change it |
| --- | --- |
| Category / Subject business `code` | `CATnnn` / `SUBnnn`, unique in its own collection and shared across localizations. Name/description edits retain the code; Subject artifacts reference Category by code. |
| Glossary `term_code` → CMS `code` | Stable term identity within one glossary collection. Term/definition edits retain it; the same code can occur in the other glossary. |
| `content_key` | Normalized chapter content state scoped by Category code, Subject code, and language. A normalized text change changes the key; chapter reordering or normalization-only whitespace changes do not. It is not permanent editorial chapter identity. |
| Strapi `documentId` | CMS-generated document identity used for API updates, localizations, and relations within the target CMS. Text updates retain it; external artifacts omit it and recreation in another database need not preserve it. |

For precision, use the [seed schemas and mappings](interfaces/seed-data-artifacts.md),
[prepared contract](interfaces/prepared-content-artifacts.md), and
[content identity implementation](../tools/gurubodh-cli/gurubodh/content_identity.py).
The [chapter/revision/chunk/snapshot identity proposal](tasks/017-cms-led-chapter-identity-registry.md)
is exploratory, not accepted runtime behavior; its proposed registry identities
must not be confused with implemented `content_key` or Strapi `documentId`.

---

## 4. Components

### 4.1 Content Preparation Layer

- **Responsibility**: Prepare legacy source content before CMS ingestion. This
  includes Unicode conversion, chapter splitting, Assignment of Subject code and Subject Category code, basic metadata generation, and other transformations needed to produce CMS-ingestion-ready artifacts.
- **Collaborates with**: consumes source in MS Word 2007 format obtained from external sources, manually obtains Subject code and Category code fom CMS system's seed data for the job configuration; produces artifacts for the future Content Ingestion Layer.
- **Boundaries — does NOT**:
  - Write finalized entries directly into the CMS.
  - Render or serve content to end users.
  - Own the published content lifecycle.
- **Current implementation**: Python utility under
  `tools/gurubodh-cli/`, currently used for legacy DOCX Unicode
  conversion, Unicode DOCX ingest, text-only chapter splitting, canonical
  proofread text/provenance publication, explicitly non-canonical local lab
  proofreading runs, derived semantic chunk generation,
  and rebuildable chapter DOCX export to local storage or Cloudflare R2. DOCX
  is a source/transient processing format for `prep-subject`; `generate-docx`
  separately renders canonical text as human-readable Word files without
  making those files authoritative.
  Production R2 batch jobs run
  in the CPU-only `gurubodh-cli` container; native Python remains the
  development and debugging path. See
  [ADR-0013](./adr/0013-use-cloudflare-r2-for-prepared-content-artifacts.md).
- **Source font support**: Approved Unicode and APS-family sources are supported,
  including newly created documents using approved Unicode fonts. Shri-Lipi/
  Sri-Lipi/Shree Dev and other unapproved families remain unsupported; see the
  [source font safety boundary](./decisions/0006-source-font-safety-boundary.md).

### 4.2 Content Ingestion Layer — planned

- **Responsibility**: Import prepared content and basic metadata artifacts into the
  CMS. Guarantee idempotent delivery so re-running an ingestion job does not
  create duplicate CMS entries.
- **Collaborates with**: consumes artifacts produced by the Content Preparation
  Layer; writes finalized entries to the CMS via its API (never via direct
  database access).
- **Boundaries — does NOT**:
  - Reach out to external source material directly.
  - Perform DOCX Unicode conversion, chapter splitting, or artifact generation.
  - Bypass the CMS's own validation/hooks by writing to its database directly.
  - Know anything about how content is rendered or consumed downstream.
- **Current implementation**: chapter-content ingestion is not implemented yet.
  Category, Subject, and glossary seed-data ingestion is implemented separately
  in the [seed-data CLI](../tools/seed-data-cli/README.md). Future chapter-content
  ingestion commands are expected to be added under the existing
  `tools/gurubodh-cli/` Python package and exposed through the
  `gurubodh` command structure.
- **Planned/recommended direction**: AWS-based ingestion workers or adapters may
  be introduced later, but no ingestion ADR has been accepted yet.

### 4.3 Metadata Generation Layer — planned

- **Responsibility**: Generates content specific metadata such as 'tags' or 'content descriptors' for Subject content already split into chapters. The objective is to keep refining and updating 'tags' as well as 'content-descriptors' so that search function and the AI chatbot to be introduced later will be able to find relevant information quickly and correctly.
- **Collaborates with**: Consumes artifacts produced by the Content Preparation
  Layer
- **Boundaries — does NOT**:
  - Does not generate metadata for a subject stored entirely in a single file.
  - Reach out to external source material directly.
  - Perform DOCX Unicode conversion, chapter splitting, or artifact generation.
  - Does NOT update generated metadata for content already present in the CMS via its API
  - Bypass the CMS's own validation/hooks by writing to its database directly.
  - Know anything about how content is rendered or consumed downstream.
- **Current implementation**: not implemented yet. Future metadata generation
  commands are expected to be added under the existing
  `tools/gurubodh-cli/` Python package and exposed through the
  `gurubodh` command structure.
- **Planned/recommended direction**: No metadata generation ADR has been accepted yet.

### 4.4 Metadata Ingestion Layer — planned

- **Responsibility**: Updates prepared content-specific metadata such as 'tags' or 'content descriptors' for content already split into chapters into the CMS.  
- **Collaborates with**: Consumes artifacts produced by the Metadata Generation Layer
- **Boundaries — does NOT**:
  - Does not generate metadata
  - Does not create content entry into CMS. This is an update operation and therefore it should fail if the content is not already found in the CMS
  - Reach out to external source material directly.
  - Perform DOCX Unicode conversion, chapter splitting, or artifact generation.
  - Bypass the CMS API when updating generated metadata for content already present in the CMS.
  - Bypass the CMS's own validation/hooks by writing to its database directly.
  - Know anything about how content is rendered or consumed downstream.
- **Current implementation**: not implemented yet. Future metadata ingestion
  commands are expected to be added under the existing
  `tools/gurubodh-cli/` Python package and exposed through the
  `gurubodh` command structure.
- **Planned/recommended direction**: No metadata ingestion ADR has been accepted yet.

### 4.5 Headless CMS (System of Record)

- **Responsibility**: Store structured content and metadata, manage the
  publishing lifecycle (draft/published/archived), expose content via API, and
  reference media assets.
- **Collaborates with**: receives implemented seed-data API writes. Chapter and
  metadata ingestion, consumption clients, and embedding/webhook integrations
  remain planned.
- **Boundaries — does NOT**:
  - Perform source-specific ingestion logic.
  - Render UI or own presentation concerns.
  - Perform semantic/vector search itself — that is the RAG layer's job, built on
    top of CMS content.
- **Current implementation**: Strapi (self-hosted). See
  [ADR-0001](./adr/0001-use-strapi-as-headless-cms.md). API style: see
  [ADR-0004](./adr/0004-strapi-api-style.md). Admin access control: see
  [ADR-0005](./adr/0005-cms-admin-access-control.md).

### 4.6 Media / Asset Storage

- **Responsibility**: Durable, Cloud-based storage for binary assets (documents,
  audio, etc.) referenced from CMS entries.
- **Collaborates with**: Likely to be the CMS - the content management system as most such systems provide plugins to collaborate with cloud storages; may be read by Web, Chat, or Mobile consumption layers, in the initial phases (often via a CDN in front of it).
- **Boundaries — does NOT**:
  - Own asset metadata (alt text, captions, relations) — that belongs to the CMS.
- **Current implementation**: None
- **Planned/recommended direction**: S3-backed storage provider for Strapi.

### 4.7 Web Consumption Layer

- **Responsibility**: Render content for end users on the web; query the CMS
  (and later the RAG Query Service) for data; manage caching/revalidation.
- **Collaborates with**: reads from CMS; in Phase 3, also calls the RAG Query
  Service for Q&A features.
- **Boundaries — does NOT**:
  - Own content data — the CMS remains the source of truth even though the web
    layer may cache it.
  - Implement content validation/business logic that belongs in Content
    Preparation or Content Ingestion.
- **Current implementation**: planned Next.js placeholder root
  `apps/gurubodh-web/`. The Next.js application has not been scaffolded yet. See
  [ADR-0002](./adr/0002-use-nextjs-for-web-frontend.md). Hosting model: see
  [ADR-0007](./adr/0007-nextjs-hosting-model-on-aws.md).

### 4.8 Chat Consumption Layer — *Phase 3*

- **Responsibility**: Render the user-facing conversational interface for
  asking questions about Gurubodh content and showing grounded answers with
  source context.
- **Collaborates with**: calls the RAG Query Service for answers; may read CMS
  APIs for source display, citations, and content previews.
- **Boundaries — does NOT**:
  - Own content data — the CMS remains the source of truth.
  - Generate embeddings, maintain vector indexes, or choose model providers
    directly.
  - Bypass the RAG Query Service for retrieval and answer-generation workflow
    orchestration.
- **Current implementation**: planned Next.js placeholder root
  `apps/gurubodh-chat/`. The Next.js application has not been scaffolded yet.
  The proposed chat/RAG workflow remains a task note, not accepted stable
  architecture. See [Task-016](./tasks/016-chat-rag-workflow.md).

### 4.9 Embedding Pipeline — *Phase 3*

- **Responsibility**: React to CMS publish/update/unpublish events; generate
  embeddings for (chunked) content; keep the Vector Store in sync with the CMS.
- **Collaborates with**: triggered by CMS webhooks; reads CMS content; writes to
  the Vector Store. 
- **Boundaries — does NOT**:
  - Generate or own content — it only derives vectors from what the CMS already
    holds.
  - Serve queries directly (that's the RAG Query Service).
- **Current implementation**: not yet decided; we need to work on how the generated embeddings work with "content descriptors metadata" prepared by future metadata generation commands to make search effective and efficient. See
  [ADR-0009](./adr/0009-embedding-model-and-llm-provider.md).

### 4.10 Vector Store — *Phase 3*

- **Responsibility**: Store and serve embeddings for similarity search.
- **Collaborates with**: written to by the Embedding Pipeline; read by the RAG
  Query Service.
- **Boundaries — does NOT**:
  - Act as a system of record for content. If lost, it must be fully rebuildable
    by re-running the Embedding Pipeline against the CMS.
- **Current implementation**: likely to be pgvector extension for PostgreSQL See
  [ADR-0008](./adr/0008-vector-database-for-rag.md).

### 4.11 RAG Query Service — *Phase 3*

- **Responsibility**: Accept a natural-language question, retrieve relevant
  chunks from the Vector Store, construct a grounded prompt, call an LLM, and
  return an answer that cites the source CMS entries.
- **Collaborates with**: called by Web, Chat, and Mobile consumption layers;
  reads from the Vector Store; calls an external/managed LLM.
- **Boundaries — does NOT**:
  - Generate answers without grounding them in retrieved CMS content and citing
    sources.
  - Become a second source of truth for content.
- **Current implementation**: not yet decided. See
  [ADR-0009](./adr/0009-embedding-model-and-llm-provider.md).

### 4.12 Mobile Consumption Layer — *Phase 4*

- **Responsibility**: Render content and Q&A features for end users on mobile,
  using the same data as the web layer.
- **Collaborates with**: reads from CMS and (Phase 3+) the RAG Query Service —
  identical integration points to the Web Consumption Layer.
- **Boundaries — does NOT**:
  - Introduce a mobile-specific backend or duplicate business logic that already
    lives behind the CMS/RAG APIs.
- **Current implementation**: not yet decided. See
  [ADR-0010](./adr/0010-mobile-app-framework.md).

---

## 5. Component Boundary Map

This table includes intended dependencies; planned integrations are not runtime
prerequisites for the implemented CMS or preparation CLI.

| Component | Depends On | Depended On By | Must Not Do |
|---|---|---|---|
| Seed-data CLI (implemented) | External CSVs, reviewed artifacts | CMS through Strapi API | Write directly to PostgreSQL |
| Prepared storage (implemented) | Content Preparation | Derived exports/chunks; future chapter ingestion | Own CMS publication state |
| Content Preparation Layer | Source DOCX files, job configuration, CMS seed-code references | Content Ingestion Layer, Metadata Generation Layer | Write finalized entries directly to CMS |
| Content Ingestion Layer | Prepared content artifacts | CMS | Convert DOCX; split chapters; bypass CMS API |
| Metadata Generation Layer | Prepared chapter-level artifacts | Metadata Ingestion Layer, future search/RAG workflows | Generate metadata for unsplit single-file subjects; update CMS directly; convert DOCX |
| Metadata Ingestion Layer | Generated metadata artifacts, existing CMS entries | CMS | Generate metadata; create new CMS content entries; bypass CMS API |
| Headless CMS | PostgreSQL; seed API writes (implemented), chapter/metadata ingestion (planned) | Web, Chat, Mobile, Embedding Pipeline | Render UI; perform vector search |
| Media Storage | CMS / storage-provider integration | Web, Chat, Mobile (via CDN) | Own asset metadata |
| Web Consumption Layer | CMS, RAG Query Service (Phase 3) | End users | Own content data; implement content validation |
| Chat Consumption Layer | CMS, RAG Query Service (Phase 3) | End users | Own content data; maintain vectors; orchestrate retrieval outside the RAG Query Service |
| Embedding Pipeline | CMS (webhooks + reads) | Vector Store | Generate/own content; serve queries |
| Vector Store | Embedding Pipeline (writes) | RAG Query Service | Act as a system of record |
| RAG Query Service | Vector Store, LLM provider | Web, Chat, Mobile | Answer ungrounded/uncited questions |
| Mobile Consumption Layer | CMS, RAG Query Service (Phase 3) | End users | Introduce a separate backend |

---

## 7. Phased Evolution

| Phase | Components Active |
|---|---|
| **Current implemented foundation** | Content Preparation with local and container/R2 workflows, Strapi CMS with Category/Subject/glossary schemas and seed-data ingestion, local PostgreSQL scripts |
| **Phase 1 target** | Content Ingestion, Content Preparation, Headless CMS, Media Storage |
| **Phase 2 target** | + Web Consumption Layer (production-hardened) |
| **Phase 3 target** | + Chat Consumption Layer, Embedding Pipeline, Vector Store, RAG Query Service |
| **Phase 4 target** | + Mobile Consumption Layer |

The component boundaries defined in Section 4 are designed to hold across all
four phases — later phases add components, they should not require redrawing
the boundaries of earlier ones.

---

## 8. Cross-Cutting Concerns (Principles, Not Implementations)

- **Authentication/Authorization**: each consumption layer authenticates its own
  end users (if/when content is gated); the CMS authenticates editors
  separately. Specific mechanisms are an ADR-level decision, not an
  architectural boundary.
- **Webhooks as the integration backbone**: any component that needs to react to
  content changes (cache invalidation, re-embedding) does so via CMS webhooks,
  not by polling or reaching into the CMS database.
- **Environment isolation**: dev/staging/production each get fully isolated
  infrastructure (no shared CMS database across environments).
- **Observability**: every component that processes data asynchronously
  (Content Ingestion, Content Preparation, Embedding Pipeline) must emit
  structured logs and failure alerts, since these stages are the easiest places
  for silent data loss.

---

## 9. Related ADRs

See [adr/README.md](./adr/README.md) for the full, evolving list of
Architecture Decision Records — including already-decided choices (CMS,
frontend, hosting platform) and currently open decisions with recommended
defaults.

---

## 10. Glossary

- **System of Record**: the component whose state is authoritative; all other
  components either feed it or derive from it.
- **Staging boundary**: a durable handoff point (queue/storage) between two
  components that decouples their failure modes.
- **RAG (Retrieval-Augmented Generation)**: answering questions by retrieving
  relevant content and grounding an LLM's response in it.
- **ADR (Architecture Decision Record)**: a short document capturing a specific
  decision, its context, and its consequences.
  
## Update Rules

<update_rules>
Update this file when a module, boundary, runtime dependency, deployment shape, or data ownership rule changes.
</update_rules>
