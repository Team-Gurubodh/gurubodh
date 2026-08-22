# Task-017: CMS-Led Chapter Identity Registry and Manifest Lineage

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-08-22</date>
<last_updated>2026-08-22</last_updated>
<owners>Gurubodh maintainers</owners>
<github_issue>208</github_issue>
<update_issue>213</update_issue>

## Goal

Maintain the coherent design foundation for Gurubodh CMS ingestion, stable
logical chapter identity, immutable published-content revisions, accepted
semantic chunks, finalized subject snapshots, and manifest lineage.

The design must make Strapi/PostgreSQL the sole system-of-record boundary while
preserving two different kinds of data ownership inside that boundary:

1. Strapi-managed editorial content that benefits from Draft & Publish,
   internationalization, content APIs, validation, and administration.
2. Protected operational records whose append-only, transactional lifecycle
   must remain outside Strapi schema synchronization and ordinary editorial
   CRUD operations.

This record is the input to a later detailed implementation plan. It defines
the responsibilities, state boundaries, invariants, and recommended persistence
model that the implementation plan must honor.

> **Implementation authority:** This task is a proposed design record. It does
> not approve CMS content types, database schemas or migrations, ingestion
> commands, R2 changes, vector-store changes, or production behavior. A separate
> GitHub Issue must accept a detailed implementation plan, executable scope, and
> acceptance criteria before implementation begins.

## Context

Chapter text can change, chapters can be inserted or retired, and an entire
subject can be reshuffled. Gurubodh therefore must not use chapter number,
title, filename, source path, or current text as the permanent identity of a
logical chapter.

At the same time, chapter text is editorial content. Editors must be able to
ingest it as a draft, modify it without changing the live version, publish it
per locale, and retain enough exact history for a finalized snapshot and its
chunks to remain reproducible after later publications.

Strapi 5 represents all locale and draft/published variations of one content
entry as one document. Its `documentId` is useful as a Strapi API locator, but
it is not a Gurubodh identity and does not identify an exact content state. See
the Strapi [document concept](https://docs.strapi.io/cms/api/document),
[Draft & Publish](https://docs.strapi.io/cms/features/draft-and-publish), and
[Internationalization](https://docs.strapi.io/cms/features/internationalization)
documentation.

Prepared artifacts introduce a separate concern. `prep-subject` and
`generate-chunks` produce candidate data before Gurubodh has reconciled stable
chapter identity or approved a complete subject release. Cloudflare R2 remains
the durable staging and audit location for those artifacts; it is not the
authority for logical identity, finalized snapshots, or published CMS content.

### Design evolution

The initial stable-identity proposal placed the registry and immutable manifest
history in R2. The subsequent CMS-led assessment moved chapter identity and
finalized lineage into Strapi/PostgreSQL while retaining R2 as prepared-artifact
staging. This revision makes that CMS-led direction precise: editorial and
retained textual content is Strapi-managed, while identity allocation and
release-control records use a protected PostgreSQL schema behind the same CMS
service boundary.

## Identity Model

The recommended model distinguishes the following identifiers:

| Identifier | Meaning | Stability and scope |
| --- | --- | --- |
| `chapter_key` | Gurubodh-issued identity of one logical chapter across translations. | UUID v4 allocated once; never recalculated or changed. |
| `(chapter_key, locale)` | One localized editorial variant of the logical chapter. | Stable across text changes in that locale. |
| `chapter_revision_key` | One retained, exact published content state for a chapter and locale. | Immutable and globally unique. |
| `chapter_number` | Position of a chapter in one finalized subject/locale snapshot. | May change in every snapshot; never identity. |
| `content_key` | Identity of exact normalized chapter text within its category, subject, and locale. | Changes when normalized text changes; provenance, not logical identity. |
| `chunk_set_key` | Identity of one accepted segmentation of an exact chapter revision under one chunking configuration. | Changes when source revision or chunking configuration changes. |
| `chunk_key` | Identity of one ordered chunk within an accepted chunk set. | Immutable within that chunk set. |
| `snapshot_id` | Identity of one immutable finalized subject/locale release. | Never reused or modified after finalization. |

### Language identity decision

The recommended first implementation makes `chapter_key` language-neutral.
Strapi can then represent translations as locales of the same Chapter document,
with stable non-localized identity fields and localized editorial fields.

Snapshots remain scoped to one subject and locale. A translation can lag,
remain a draft, use a different chapter order, or be absent without changing
the identity of the logical chapter in another locale. Each localized published
state receives its own `chapter_revision_key` and `content_key`.

If implementation research finds a hard requirement for an independently
addressable language-edition identifier, it may add a `chapter_locale_key`.
That key would supplement, not replace, the language-neutral `chapter_key`.
Using a different `chapter_key` for every locale is not the recommended model
because it would work against Strapi's native localization document model.

## System-of-Record Boundaries

"Strapi/PostgreSQL is the system of record" does not mean that every record is
an editable Strapi collection type. It means that authoritative content and
control records live behind the CMS service boundary and that external tools
must not bypass that boundary or establish another authority.

The recommended PostgreSQL layout uses separately owned schemas in the same
database:

```text
PostgreSQL database
├── gurubodh_cms       Strapi-managed content types and Strapi internal tables
├── gurubodh_registry  protected identity, ingestion, and snapshot records
└── gurubodh_rag       derived vector and RAG-readiness records, if colocated
```

Using one database permits a short finalization transaction to coordinate
content and registry writes when the supported Strapi transaction boundary is
confirmed. Schema ownership and privileges must nevertheless prevent Strapi's
automatic content-schema synchronization from treating registry or RAG tables
as its own.

The CMS application already supports a PostgreSQL `DATABASE_SCHEMA` setting.
The implementation should set it explicitly to the Strapi-owned schema instead
of relying on `public`. Strapi also warns that schema synchronization can remove
unknown tables; protected tables must therefore not be placed in the configured
Strapi schema. See Strapi's [database configuration](https://docs.strapi.io/cms/configurations/database)
and [database migration](https://docs.strapi.io/cms/database-migrations)
documentation.

### Record ownership matrix

| Record or artifact | Authoritative owner/location | Strapi content type? | Lifecycle |
| --- | --- | --- | --- |
| Category and Subject | `gurubodh_cms` | Yes; existing first-class content | Editorial Draft & Publish and i18n as configured. |
| Chapter editorial workspace | `gurubodh_cms` | Yes; first-class `Chapter` | Localized draft, modified, published, or unpublished state. |
| Retained Chapter Revision | `gurubodh_cms` | Yes; protected first-class content | Immutable capture of one exact published Chapter locale. |
| Accepted Chunk Set | `gurubodh_cms` | Yes; protected technical content | Immutable derivation of one Chapter Revision. |
| Accepted Chunk text | `gurubodh_cms` | Yes; protected technical content | Immutable member of one accepted Chunk Set. |
| Logical chapter identity allocation | `gurubodh_registry` | No | Controlled creation; immutable identity and scope. |
| Ingestion job and idempotency result | `gurubodh_registry` | No | State machine and audit history. |
| Reconciliation mapping and operator decision | `gurubodh_registry` | No | Append-only evidence for matching, ambiguity, and approval. |
| Finalized snapshot and lineage | `gurubodh_registry` | No | Immutable, append-only release record. |
| Snapshot membership and `chapter_number` | `gurubodh_registry` | No | Immutable ordered membership within one snapshot. |
| Current-snapshot pointer | `gurubodh_registry` | No | Controlled compare-and-swap pointer per subject/locale. |
| Retirement event | `gurubodh_registry` | No | Explicit approved event; never inferred from absence. |
| Candidate prepared text, manifests, and chunks | R2 or local development storage | No | Staging and audit artifacts; not finalized authority. |
| Embedding configuration, vectors, job state, and RAG-ready pointer | Derived vector store or `gurubodh_rag` | No | Rebuildable derivation with pending, ready, or failed state. |

### Database privilege boundary

- A registry migration role owns `gurubodh_registry` objects. Strapi content
  schema synchronization has no create, alter, or drop privileges there.
- The server-side CMS ingestion/finalization service receives only the registry
  operations it needs, preferably through constrained DML grants or stored
  procedures. It does not receive unrestricted registry DDL or deletion rights.
- External preparation and ingestion clients use protected CMS endpoints. They
  never connect directly to Strapi, registry, or vector-store tables.
- Registry records refer to content through Gurubodh stable keys. They must not
  depend on Strapi numeric row IDs. A `documentId` may be retained as a locator,
  but `chapter_key`, `chapter_revision_key`, `content_key`, and locale carry the
  durable semantics.
- The registry is the authoritative allocator of `chapter_key`; the matching
  non-localized Chapter field is an immutable correlation key and must agree
  exactly with its registry record.
- Cross-schema foreign keys to Strapi implementation tables should not be
  assumed. The finalization service must validate stable-key correspondence and
  database constraints must protect each schema's own invariants.

## First-Class Strapi Content Model

### Chapter

Chapter is the editor-facing aggregate and must benefit from native Strapi
content management.

Recommended characteristics:

- Draft & Publish enabled.
- Internationalization enabled.
- `chapter_key` immutable and non-localized.
- Subject relationship and other identity-bearing classification fields
  non-localized unless a later content-model decision gives them locale-specific
  meaning.
- Title, chapter text, summary, and editorial metadata localized as appropriate.
- `content_key` and normalized checksum computed for each locale and protected
  from ordinary editor input.
- `chapter_number` excluded as an identity field. Authoritative display order is
  resolved through current snapshot membership.

An external import creates or updates a localized draft. It must not overwrite
the published locale merely because candidate artifacts changed. Editors or an
authorized controlled workflow decide when that locale is ready to publish.

### Retained Chapter Revision

Native Draft & Publish preserves a live published version while newer draft
changes are being edited, but it is not the application-level immutable ledger
required by historical snapshots. Strapi Content History, where licensed, can
improve editorial recovery; it must not replace Gurubodh revision and snapshot
records because its purpose is editor-facing restore into the current draft.

For every distinct published text accepted for finalization, the CMS must
materialize a protected Chapter Revision containing at least:

- `chapter_revision_key`, `chapter_key`, and locale;
- exact retained chapter text and localized editorial fields needed to render
  or rebuild derived data;
- `content_key`, normalization contract, and checksums;
- source-manifest and ingestion provenance;
- the Strapi Chapter `documentId` as an optional locator, not identity; and
- creation/finalization timestamps and service actor provenance.

The revision is a Strapi-managed content type because its text remains CMS
content. It should not have independent Draft & Publish controls: it represents
an already accepted published state. Generic create, update, and delete routes
and ordinary Content Manager editing must be disabled or tightly restricted.
It should also use an explicit immutable locale field instead of enabling native
i18n, because each revision represents one exact localized state rather than an
editorial document with translatable variants.

Saving a Chapter draft may replace earlier draft work. When finalization accepts
distinct published normalized text, it creates a new retained revision.
Finalizing unchanged published content must be idempotent and must not create
duplicate revision history.

### Accepted Chunk Set and Chunk

Accepted chunk text is also CMS-owned content, but it must not be independently
publishable or independently localized.

Each Chunk Set belongs to exactly one Chapter Revision and records the exact
source identity, chunking configuration, manifest binding, checksums, and
ordered chunk count. Each Chunk belongs to exactly one Chunk Set and records its
stable key, order, text, spans, checksums, and token-counting provenance.

The chunk locale is inherited from its Chapter Revision. A translation produces
a different localized Chapter Revision and therefore a separately generated
Chunk Set. Editors cannot translate a chunk independently of its chapter or
publish a mixture of chunks from different revisions.

Chunk Set and Chunk should have native i18n and Draft & Publish disabled. Their
explicit locale and effective availability are inherited from the immutable
Chapter Revision and finalized snapshot to which they belong.

Candidate chunks may be generated before reconciliation, as they are today.
They remain staging artifacts until ingestion verifies their binding to the
exact candidate chapter, resolves the `chapter_key`, and attaches them to the
accepted Chapter Revision. Retrieval embeddings are not stored with candidate
or accepted chunk content; they are produced later from a finalized snapshot.

Separate Chunk and Chunk Set content types are preferred over treating chunks
as anonymous repeatable components because downstream provenance, stable chunk
references, protected access, and independent embedding derivations require
addressable records. The detailed implementation plan must validate this choice
against expected volume and Strapi query behavior.

## Independent Lifecycle Axes

The implementation must keep three lifecycle axes separate:

| Axis | States | Authority and meaning |
| --- | --- | --- |
| Editorial content | draft, modified, published, unpublished; per locale | Strapi Chapter lifecycle. Published means editorially approved, not necessarily in the current subject snapshot. |
| Subject release | planned, finalized, current, superseded; plus explicit retirement events | Registry lifecycle. Current means the complete subject/locale snapshot is authoritative for CMS readers. |
| RAG derivation | pending, ready, failed; per snapshot and embedding configuration | Vector layer. Ready means retrieval data is complete for that exact finalized snapshot and configuration. |

A Chapter locale can be published but not yet current because the rest of its
subject release is incomplete. A current CMS snapshot can exist while embedding
generation for it is pending or failed. RAG readers may therefore use an older
fully ready snapshot while CMS readers use the newer current snapshot.

Publishing or unpublishing the mutable Chapter workspace does not rewrite an
existing finalized snapshot. If a current released chapter must be withdrawn,
an authorized workflow must create a new snapshot transition that removes the
locale variant from current authoritative reads while preserving historical
snapshot evidence. Generic unpublish is not an emergency snapshot-deletion
mechanism.

Strapi publishes one locale at a time. Finalization must consequently scope all
validation, revision capture, membership, and current pointers to a declared
subject and locale. A batch workflow may coordinate several locales, but each
locale has an independently valid snapshot transition.

## Candidate-to-Finalized Architecture

```text
prep-subject
    -> candidate chapter manifest, normalized text, content_key, R2 artifacts
generate-chunks
    -> candidate Chunk Sets bound to the exact candidate manifest
CMS ingestion workflow
    -> validate, reconcile, allocate chapter_key, create/update Chapter drafts
Strapi editorial workflow
    -> review and publish localized Chapter content
CMS finalization service
    -> capture immutable Chapter Revisions and accepted Chunks
    -> atomically write finalized registry snapshot and advance current pointer
CMS snapshot API
    -> serve complete current or historical subject/locale snapshots
Embedding Pipeline
    -> derive vectors only from an immutable finalized CMS snapshot
Vector store
    -> maintain per-configuration RAG-ready snapshot pointers
```

The candidate manifest is a portable preparation handoff, not a finalized
logical-identity manifest. A finalized manifest is a rendering of authoritative
CMS and registry records. R2 export of that rendering is optional and must never
become a second registry or current-snapshot authority.

## Proposed Reconciliation and Finalization Flow

1. Ingestion receives a candidate chapter manifest and the matching candidate
   semantic manifest when chunks are required. It verifies referenced artifacts,
   checksums, chapter numbers, content identity, and exact manifest binding
   before model work or authoritative writes.
2. The CMS service creates or resumes an ingestion job with an idempotency key,
   source checksum, declared subject/locale, and `base_snapshot_id` read from the
   current registry pointer.
3. Reconciliation applies recorded operator mappings first, then unique safe
   matches. Exact `content_key` equality is evidence but cannot by itself choose
   between duplicate logical chapters. Ambiguity, missing chapters, and proposed
   retirements block finalization.
4. The service allocates a UUID v4 `chapter_key` only for an approved new logical
   chapter. Allocation and the resulting mapping are preserved independently of
   subsequent text or order changes.
5. Ingestion creates or updates each localized Chapter draft through the CMS
   service boundary. Candidate Chunk Sets remain private staging data associated
   with the ingestion job. No candidate import advances the current pointer.
6. Editors or an authorized controlled workflow review and publish the intended
   Chapter locales. Publishing unrelated chapters individually does not make a
   partial subject release authoritative.
7. Finalization explicitly reads the published status and locale for every
   planned member, verifies its `content_key`, and creates or reuses the exact
   immutable Chapter Revision. It accepts only the Chunk Set bound to that exact
   revision and chunking configuration. If editorial changes made the candidate
   chunks stale, finalization blocks until a matching Chunk Set exists. Default
   API behavior must never be relied upon when choosing draft versus published
   data.
8. Long-running artifact transfer and chunk validation finish before the final
   transaction. The short transaction rechecks `base_snapshot_id` and every
   planned published locale/revision binding, writes any required protected
   content records, inserts immutable snapshot membership and retirement events,
   stores finalized-manifest provenance, advances the current pointer, and marks
   the ingestion job finalized.
9. A concurrent pointer change aborts finalization and requires reconciliation
   against the new base snapshot. A failed transaction or candidate import cannot
   expose a partial snapshot.
10. A post-finalization Embedding Pipeline reads the immutable snapshot through
    the CMS snapshot API, writes derived vectors through the vector-store
    boundary, and records pending, ready, or failed status for its embedding
    configuration.
11. CMS consumers resolve chapters and order through the current snapshot API.
    RAG consumers resolve the latest fully ready snapshot for the selected
    embedding configuration. Generic content routes must not be treated as the
    authoritative complete-subject release API.

## Registry and Content Invariants

- A `chapter_key` is globally unique, language-neutral, belongs to one logical
  subject chapter, and is immutable after allocation.
- A Strapi `documentId` is an implementation locator across draft/published and
  localized variants. It must never replace `chapter_key` or
  `chapter_revision_key` in Gurubodh contracts.
- `chapter_number` is unique and contiguous only within one finalized
  subject/locale snapshot. It is never used for reconciliation identity.
- A finalized snapshot contains exactly one membership row for each active and
  available `(chapter_key, locale)` variant intended for its declared
  subject/locale, and each included chapter number.
- Every snapshot membership pins an exact `chapter_revision_key`, `content_key`,
  locale, and accepted `chunk_set_key` when chunks are required. It never points
  only to the mutable Chapter document.
- A finalized snapshot links to its preceding finalized snapshot. The service,
  not an external client, derives `previous_snapshot_id` from current registry
  state.
- Published and current are different states. Only the snapshot-aware CMS API
  determines the authoritative complete subject release.
- Publishing, modifying, or unpublishing a Chapter locale cannot mutate an
  already finalized snapshot. Removal from current reads requires a controlled
  snapshot transition; historical membership remains retained.
- A retirement is an explicit approved registry event. Absence from a candidate
  manifest is a conflict or missing-chapter report, never automatic deletion,
  unpublishing, or retirement.
- Logical chapter retirement is language-neutral. A missing, lagging,
  unpublished, or withdrawn locale is not by itself retirement of the logical
  chapter and must be represented through locale-specific content and snapshot
  state.
- A `content_key` identifies exact normalized text and may be shared by duplicate
  text. It must not alone select a logical chapter.
- Every accepted Chunk Set binds to one exact Chapter Revision and candidate
  manifest checksum. Chunks from different revisions or manifests cannot be
  mixed.
- Chapter Revisions, accepted Chunk Sets, accepted Chunks, finalized snapshots,
  memberships, and retirement history are immutable after finalization.
- An idempotent retry returns the existing job outcome and cannot allocate new
  keys, duplicate revisions, or advance the current pointer twice.
- No embedding state gates or rolls back the CMS current-snapshot pointer.
  Vector records remain derived and rebuildable.
- Strong retention depends on database privileges, backups, point-in-time
  recovery, and any separately approved immutable exports; application-level
  immutability alone is not a backup policy.

## API and Administration Safeguards

- External preparation and ingestion tools use a custom protected CMS ingestion
  endpoint. They do not issue a client-side series of unrelated generic REST
  writes and never write PostgreSQL directly.
- The finalization endpoint performs authorization, validation, idempotency,
  concurrency checks, and the short authoritative transaction server-side.
- Chapter remains available in the Content Manager for normal localized
  editorial work. Stable identity and computed provenance fields are read-only
  or hidden from ordinary editors.
- Chapter Revision, Chunk Set, and Chunk are Strapi-managed but protected. Their
  generic create/update/delete endpoints and ordinary editorial surfaces are
  disabled or restricted to the controlled service.
- Registry and snapshot records are not exposed as normal Draft & Publish
  content. Operator reconciliation and retirement decisions use a purpose-built
  restricted workflow rather than direct table editing.
- Public CMS consumers receive published content through snapshot-aware APIs.
  Preview or editorial APIs may expose drafts only with explicit authorization
  and must clearly identify draft status and locale.
- Webhooks and embedding jobs carry stable Gurubodh keys, exact revision and
  snapshot identifiers, and locale. A generic Chapter update webhook alone is
  insufficient evidence that a new complete release is ready.

## Current Repository Observations

- `prep-subject` currently produces a schema-v1
  `chapter_content_manifest.json` containing generated chapter number,
  `content_key`, checksums, and artifact references. It has no `chapter_key`,
  `chapter_revision_key`, snapshot ID, lineage, or retirement history
  ([prepared-content interface](../interfaces/prepared-content-artifacts.md)).
- `generate-chunks` consumes the candidate chapter manifest as its authoritative
  selected set and emits schema-v2 candidate chunks bound to the exact manifest.
  It does not allocate logical chapter identity or persist retrieval vectors.
  [GitHub Issue #210](https://github.com/Team-Gurubodh/gurubodh/issues/210)
  is the implementation authority for that breaking candidate-chunk contract.
- The Strapi application currently has Category, Subject, Sanatan Glossary, and
  Prabodhan Glossary content types. It has no Chapter, Chapter Revision, Chunk
  Set, Chunk, snapshot, retirement, or ingestion-job implementation.
- The existing Category and Subject content types already demonstrate Draft &
  Publish, i18n, and localized versus non-localized fields. The future Chapter
  model should follow those conventions where their semantics match.
- Local and R2 overwrite behavior does not provide an atomic versioned release.
  [Decision-0003](../decisions/0003-prepared-artifact-ownership-and-lifecycle.md)
  explicitly deferred versioned releases and a current pointer until CMS
  ingestion required them.
- [ADR-0013](../adr/0013-use-cloudflare-r2-for-prepared-content-artifacts.md)
  establishes R2 as durable storage for prepared artifacts. It does not make R2
  the logical identity registry, CMS content store, or finalized-manifest
  authority.
- The CMS application currently pins Strapi 5.50.1 and parameterizes its
  PostgreSQL schema through `DATABASE_SCHEMA`. No protected registry schema or
  role boundary has been implemented.

## Inputs Required in the Detailed Implementation Plan

The subsequent implementation plan must define and verify at least:

1. Exact Strapi schemas, fields, relations, localization flags, visibility,
   validation, indexes, and uniqueness behavior for Chapter, Chapter Revision,
   Chunk Set, and Chunk.
2. Exact `gurubodh_registry` tables, constraints, append-only enforcement,
   current-pointer concurrency control, migration ownership, and database roles.
3. The supported Strapi transaction mechanism for coordinating protected
   content and registry writes without bypassing Strapi content behavior.
4. Ingestion, reconciliation-plan, approval, finalization, current/historical
   snapshot, and preview API contracts, including authorization and response
   sanitization.
5. How Chapter draft imports interact with manual editor changes, optimistic
   concurrency, locale selection, publish permissions, and batch release UX.
6. The normalized-content, revision-key, Chunk Set, chunk-key, manifest
   checksum, and idempotency contracts.
7. Migration and compatibility handling for existing schema-v1 candidate
   manifests and prepared artifact trees.
8. Verification for insertion, reshuffling, text changes, duplicate content,
   ambiguous matches, translation lag, retirement, unchanged retries,
   concurrency, partial publication, unpublish/withdrawal behavior, rollback,
   and failed embeddings.
9. Backup, restore, point-in-time recovery, retention, and optional immutable
   export procedures for protected registry and retained content history.
10. Performance tests for expected chapter and chunk volume and the decision to
    retain separate Chunk records rather than another Strapi representation.

## Questions Still Open

These questions do not change the ownership and lifecycle foundation above, but
the detailed implementation plan must resolve them:

1. Which Strapi field types should store exact chapter and chunk text, and which
   localized editorial metadata belongs on Chapter versus Chapter Revision?
2. Does implementation require a separate `chapter_locale_key`, or is the
   composite `(chapter_key, locale)` sufficient for every external contract?
3. Should a controlled batch action publish all planned Chapter locales, or
   should finalization consume entries published individually by editors?
4. Should an identical candidate rerun record only a no-op ingestion job, or
   create a finalized snapshot with identical membership for audit purposes?
5. Must finalized manifests retain byte-for-byte original JSON in addition to
   canonical relational rows, canonical serialization, and checksums?
6. What retention period, backup objective, restore test, and optional WORM
   export are required for registry history and retained Chapter Revisions?
7. Will the derived vector store use a separate database or a separately owned
   `gurubodh_rag` schema in the CMS PostgreSQL database?
8. What lag reporting and operational policy should retrieval use while a newer
   current CMS snapshot is pending or failed for an embedding configuration?

## Approved Plan

None. This document defines the recommended architecture foundation and the
constraints a future implementation plan must satisfy. A separate GitHub Issue
must approve implementation scope and acceptance criteria before any CMS schema,
database migration, ingestion service, R2 contract, or vector-store behavior is
changed.

## Execution Results

- [GitHub Issue #208](https://github.com/Team-Gurubodh/gurubodh/issues/208)
  established the original documentation-only Task-017 scope.
- [GitHub Issue #213](https://github.com/Team-Gurubodh/gurubodh/issues/213)
  authorized the coherent CMS ingestion, Strapi lifecycle, and record-ownership
  revision of this task.
- The task now distinguishes Strapi editorial content, immutable CMS content
  revisions and chunks, protected registry data, prepared R2 artifacts, and
  derived RAG data.
- No production code, CMS schema, database migration, artifact contract,
  infrastructure behavior, or vector-store behavior was changed.

## Follow-Up

- Review and accept or revise this proposed foundation before creating the
  detailed implementation issue.
- Promote the accepted durable architecture into an ADR when maintainers are
  ready to make the persistence and ownership boundary binding.
- Create the detailed implementation plan and implementation issue only after
  the remaining questions have explicit answers, testable acceptance criteria,
  and a safe migration sequence.
