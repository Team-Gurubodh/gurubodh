# Task-017: CMS-Led Chapter Identity Registry and Manifest Lineage

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-08-22</date>
<owners>Gurubodh maintainers</owners>
<github_issue>208</github_issue>

## Goal

Maintain a living design record for a stable Gurubodh logical chapter identity
registry, complete finalized-manifest lineage, and deterministic ingestion into
the CMS. The record must preserve the present assessment and be updated by later
design discussions until a separate GitHub Issue accepts a final implementation
plan.

## Context

Gurubodh needs three distinct concepts:

| Field | Meaning | Stability |
| --- | --- | --- |
| `chapter_key` | Gurubodh-issued identity of a logical chapter. | Never changes. |
| `chapter_number` | Current chapter position within a subject. | May change. |
| `content_key` | Identity of the exact normalized chapter content. | Changes when text changes. |

The source documents do not provide a sufficiently stable chapter identifier.
Accordingly, a logical chapter must receive one UUID v4 `chapter_key` when it
first enters the Gurubodh registry. The key is preserved by reconciliation; it
must never be recalculated from text, chapter number, filenames, titles, or
preparation configuration.

The attached *Gurubodh Stable Chapter Identity Plan* (2026-08-20) proposed an
R2-backed identity registry and immutable `chapter_content_manifest.json`
history. The subsequent CMS-led alternative assessment recommends that
Strapi/PostgreSQL instead become the sole authority for chapter identity and
finalized manifest lineage, while R2 remains durable prepared-artifact staging.

This direction accords with the architecture principle that the CMS is the
system of record and that preparation and ingestion remain separate
([architecture](../architecture.md)). It also continues the distinction already
established by [Task-015](015-chapter-versioning-and-RAG-vrchitecture.md):
`content_key` is exact-content provenance, not a stable editorial identity.

> **Implementation authority:** This task records evolving design discussion.
> It does not approve an implementation, an ADR, CMS schemas, database
> migrations, ingestion commands, R2 changes, or vector-store changes. A future
> implementation requires a separate GitHub Issue with an accepted scope, plan,
> and acceptance criteria.

## Current Repository Observations

- `prep-subject` currently produces a schema-v1
  `chapter_content_manifest.json`. It lists the current generated chapter set,
  `generated_chapter_number`, `content_key`, checksums, and artifact references,
  but it has no `chapter_key`, snapshot ID, lineage, retirement record, or
  history ([prepared-content interface](../interfaces/prepared-content-artifacts.md)).
- `generate-chunks` propagates source `content_key` but does not know a stable
  logical `chapter_key` or a preparation snapshot. It currently discovers
  prepared chapter files from the text-and-metadata directory.
- The Strapi application has no Chapter, chapter-revision, content-snapshot,
  retirement, or ingestion-job content type. Content ingestion remains future
  work ([architecture](../architecture.md)).
- Current local and R2 overwrite behavior does not provide an atomic,
  versioned release. This was explicitly deferred in
  [Decision-0003](../decisions/0003-prepared-artifact-ownership-and-lifecycle.md).
- [ADR-0013](../adr/0013-use-cloudflare-r2-for-prepared-content-artifacts.md)
  establishes R2 as durable storage for prepared artifacts. It does not require
  R2 to be the logical chapter registry.

## Current Recommendation

Use a CMS-led identity registry with a candidate-to-finalized boundary:

```text
prep-subject
    -> candidate chapter manifest and prepared artifacts
generate-chunks
    -> candidate chunks and embeddings
ingestion reconciliation
    -> resolve or allocate chapter_key values
Strapi/PostgreSQL
    -> finalized snapshot, lineage, current pointer, and retirements
```

The candidate manifest remains a portable handoff from preparation. It is not a
finalized logical-identity manifest. Ingestion must load that candidate,
reconcile it against the current CMS snapshot, and create the finalized v2
manifest inside the registry. A Strapi API may render the current or historical
finalized manifest as JSON for downstream consumers; R2 export of that JSON is
optional and must not become a second authority.

| Responsibility | Proposed owner |
| --- | --- |
| DOCX conversion, splitting, normalized checksums, and candidate `content_key` | `prep-subject` |
| Candidate chunk and embedding production | `generate-chunks` |
| Candidate validation and reconciliation planning | Content ingestion workflow |
| UUID v4 `chapter_key` allocation and preservation | Strapi ingestion service / PostgreSQL registry |
| Operator decisions for ambiguity and retirement | Controlled ingestion workflow |
| Finalized snapshot lineage and current-snapshot pointer | PostgreSQL registry |
| Prepared text, DOCX, metadata, and audit artifacts | R2 or local development storage |
| Vector retrieval data | Derived vector store |

## Proposed Registry Invariants

- A `chapter_key` is globally unique, belongs to one declared subject/language
  scope, and is immutable after allocation.
- `chapter_number` is a snapshot membership/order field. It is unique and
  contiguous within one active subject/language snapshot, but it is never used
  to identify a logical chapter.
- A current snapshot has exactly one entry for each active `chapter_key` and
  chapter number.
- A finalized snapshot links to its preceding finalized snapshot. The service,
  not an external client, determines `previous_snapshot_id` from the current
  registry state.
- A retirement is an explicit, approved event. Absence from a candidate set is
  a conflict or a missing-chapter report, never an automatic deletion.
- A `content_key` is evidence for exact normalized content and may be shared by
  duplicate chapter text. It must not alone select a logical chapter.
- Ambiguous correspondence blocks finalization until an operator supplies a
  recorded decision.
- A failed candidate import cannot advance the current finalized snapshot.
- The identity registry and snapshot history are append-only application data.
  Database privileges, backup/point-in-time recovery, and optional immutable
  exports are required if stronger retention guarantees are needed.

## Proposed Finalization Flow

1. Ingestion receives a candidate chapter manifest and, when required, the
   matching candidate semantic manifest. It verifies all referenced artifacts,
   checksums, chapter numbers, and content identity before changing registry
   state.
2. The workflow records an ingestion job with a `base_snapshot_id`, source
   manifest checksum, plan, status, and idempotency key.
3. Reconciliation applies explicit operator mappings first, then unique exact
   `content_key` matches, safe neighbour-based update proposals, new chapter
   proposals, missing-chapter reports, and conflict detection.
4. The workflow persists operator approval for every ambiguous mapping and
   retirement. No unresolved plan may be finalized.
5. Required chapter content, chunks, and embeddings are staged under the
   candidate import or snapshot identifier. No long-running file transfer or
   model work belongs inside the final database transaction.
6. A short finalization transaction verifies that the registry still points to
   `base_snapshot_id`, inserts any new identities, writes immutable snapshot
   membership and retirement events, updates the current pointer, and marks the
   job finalized. A concurrent change requires replanning.
7. Downstream readers use the current finalized snapshot. A retry using the same
   idempotency key returns its existing outcome rather than allocating new keys.

## Design Constraints and Safeguards

- External ingestion tools must use the Strapi API boundary; they must not write
  directly to PostgreSQL. The atomic operation should be a custom,
  server-side Strapi ingestion service rather than a client-side series of
  unrelated REST writes.
- Registry and snapshot records should not be normal editable Draft & Publish
  content. They need controlled writes, immutable fields, hidden or restricted
  administration surfaces, and database constraints in addition to application
  validation.
- Strapi `documentId` remains a Strapi implementation identity. Gurubodh
  workflows use the separate `chapter_key`.
- If chunks are generated before reconciliation, ingestion must bind every
  accepted chunk artifact to the exact candidate chapter entry, then attach the
  resolved `chapter_key`, content state, snapshot ID, and embedding
  configuration in durable derived records.
- The current generator should eventually bind the semantic manifest to a
  source candidate-manifest checksum or preparation-run identifier. Until then,
  ingestion must compare every chapter number, `content_key`, source checksum,
  and artifact reference before it treats the two manifests as one candidate
  release.
- If vectors reside outside the CMS database, use pending/ready/finalized
  states instead of assuming a distributed database transaction. The current
  CMS snapshot advances only after required derived data is ready.

## Questions Still Open

1. Is a logical `chapter_key` scoped independently for each language, or should
   future translations share one language-neutral logical chapter with separate
   language variants? The current recommendation is to scope first-generation
   identity to subject and language until a translation model is explicitly
   designed.
2. What is the separate revision policy for changed chapter text:
   `overwrite_current`, retained revisions, or both? This is related to, but
   must not be conflated with, logical chapter identity.
3. Should the existing output filename remain
   `chapter_content_manifest.json` while it denotes a candidate manifest, or
   should a later compatibility plan introduce a clearer candidate name?
4. Must historical manifests retain byte-for-byte original JSON, or are
   canonical serialized JSON plus a checksum and normalized relational snapshot
   rows sufficient?
5. Should an identical rerun record a no-op ingestion job only, or create a new
   finalized snapshot with identical membership?
6. Which required chunks and embedding configurations must be ready before a
   snapshot can become current, particularly before production RAG exists?
7. Will registry constraints and the finalization endpoint be implemented as
   protected Strapi content types, a Strapi plugin/service with internal tables,
   or another Strapi-supported persistence boundary?
8. What retention, backup, restore, and optional WORM-export requirements are
   necessary for finalized snapshot history?

## Approved Plan

None. The CMS-led registry is the current recommendation, not an accepted
implementation plan. Future design conversations must update this task record
with dated conclusions, changed assumptions, and resolved questions. Once the
design is accepted, create a separate implementation issue; that issue takes
precedence over this historical record.

## Execution Results

- Created [GitHub Issue #208](https://github.com/Team-Gurubodh/gurubodh/issues/208)
  to scope this documentation-only task.
- Added this Task-017 living record, preserving the R2-backed-plan context and
  the latest CMS-led alternative assessment.
- No production code, CMS schema, database migration, artifact contract, or
  infrastructure behavior was changed.

## Follow-Up

- Use this document as the single evolving record for follow-up architecture
  conversations about this proposal.
- Update its recommendation, conclusions, and open questions after each
  substantive discussion while retaining prior rationale where it remains
  relevant.
- Create an ADR only when maintainers explicitly decide the durable
  architecture. Create a separate implementation issue only after an accepted
  plan defines executable scope and acceptance criteria.
