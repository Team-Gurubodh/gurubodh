# Task-015: Chapter Versioning and RAG Architecture

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-07-25</date>
<owners>Team Gurubodh</owners>
<github_issue>176</github_issue>

## Goal

Define the proposed chapter-versioning and RAG-derivation model before CMS,
ingestion-pipeline, database, or RAG implementation work begins.

## Context

Chapter text may change after it has been saved to the CMS or Cloudflare R2, either through the
CMS UI or by reimporting externally changed content. Gurubodh needs a
deterministic way to distinguish a correction that replaces current text from a
substantive change that retains history as a new revision.

Text chunks and vector embeddings are derived from chapter content. They must
therefore follow the same decision and remain traceable to the exact chapter
text from which they were created.

> **Implementation authority:** This task preserves historical design
> exploration. It neither approves nor mandates an implementation. Any future
> implementation must be authorized by a separate GitHub Issue; that issue's
> scope, accepted plan, and acceptance criteria take precedence. Do not infer
> implementation requirements from this task.

## Design Options Considered

- A logical chapter has a stable `chapter_key` that does not change when its
  text changes. UUID v5 with a Gurubodh-owned namespace is an appropriate
  deterministic implementation when derived from immutable identity,
  such as category code, subject code, chapter number, and language.
- A retained content state has an immutable `chapter_revision_key` and a
  monotonically increasing revision number within its logical chapter.
- Every revision stores a SHA-256 checksum of normalized chapter text. The
  checksum is an integrity and duplicate-detection fingerprint, not the chapter
  identity.
- The importer has exactly two explicit editorial policies:
  `overwrite_current` and `create_revision`.
- In the existing implementation, `gurubodh` has the `--overwrite` flag.
  The `overwrite_current`  policy should improve the present `--overwrite` flag implementation
  according to the design intent captured here.
- The `create_revision` should become a new implementation within the `gurubodh prep-subject` command.
  If the incoming checksum equals the current revision checksum, the import
  should complete as `skipped_unchanged`. It does not write chapter text or rebuild
  chunks and embeddings. This is internal idempotency behavior. In the current implementation,
  `prep-subject` exists when destination directory exists or files exists in the destination
  directory. The present implementation should exit only after confirming that incoming checksum
  equals the current revision checksum and the the import should complete as `skipped_unchanged`.
- If `create_revision` receives content that differs from the current revision
  but matches an older retained revision, reject the operation rather than
  creating duplicate history. The result must identify the matching revision.
- Chunks belong to a chapter revision. Embeddings belong to a chunk and an
  `embedding_config_key` that identifies the provider, model, mode, dimensions,
  normalization, and schema/strategy details required to compare vectors safely.
- The RAG store remains derived and rebuildable. Strapi will become the content
  system of record once it is ready. However, till Strapi schema is under development,
  these design decisions should be implemented and available for testing,
  review and verification when the destination is local file system or Cloudflare R2.

## Proposed Workflow

```text
Incoming text + logical chapter identity + selected policy
                         |
                         v
             Resolve chapter by chapter_key
                         |
                         v
      Normalize text and calculate content_sha256
                         |
                         v
          Compare with current revision checksum
                         |
              +----------+----------------+
              |                           |
              v                           v
      Checksums equal             Checksums differ
              |                           |
              v                           v
  success: skipped_unchanged     overwrite_current or create_revision?
  no writes; no RAG rebuild           |                         |
                                      |overwrite_current        |create_revision
                                      |                         |
                                      v                         v
                         update current revision     matches older revision?
                         replace its RAG data           |                |
                              |                      no |                | yes
                              |                         v                v
                              |          create next revision        reject with
                              |          retain prior revision       matching details
                              |                         |
                              v                         v
                      regenerate chunks           regenerate chunks
                            and                       and
                      required embeddings         required embeddings
                                                        |
                                                        v
                                              activate new revision
                                              only when RAG data is ready
```

## RAG Storage and Retrieval Notes

- A chunk is a text segmentation result. An embedding is a vector derived from
  a chunk under one embedding configuration. Their lifecycle differs: changing
  chunking requires chunks and embeddings to be rebuilt; changing embedding
  provider/model/configuration requires only embeddings to be rebuilt.
- Even in the first implementation, when we store only one active embedding per chunk,
  chunks and embeddings may be stored in two separate  physical tables
  The conceptual identities should remain separate so a later model migration or
  multiple vector forms do not require reworking source-content ownership.
- A split chunks/embeddings design is expected to be practical at the planned
  scale of 10,000 to 15,000 chapters. Retrieval should run vector search first,
  filter to one `embedding_config_key`, and join only the small nearest-candidate
  set to chunk text and revision metadata.
- An import job should record its status, selected policy, actor/source, source
  identifier, source checksum, result revision, chunking configuration,
  embedding configuration, timestamps, errors, and retry information.
- For a new revision, do not set it as current until its required chunks and
  production embeddings are ready. This avoids CMS text being newer than the
  content available to chat retrieval.

## Deferred Scope

- **Concurrent independent write protection:** There is currently one entry
  point, so an expected-current-checksum guard is not required yet. Add it only
  when CMS UI edits and external imports can independently write the same
  chapter.
- **Revision restore:** A future operator-led `restore_revision` workflow should
  display retained revisions and require the operator to select one. It is not
  part of the present ingestion-policy design.
- Automatic classification of correction versus paraphrase, full document merge
  behavior, and line-level conflict resolution.

## Historical Record

- Preserve this task note as historical reference for the options discussed.
- Do not treat the model as an implementation baseline. A future implementation
  issue must independently define and approve its scope.
- A future implementation may revisit
  [ADR-0008](../adr/0008-vector-database-for-rag.md) and
  [ADR-0009](../adr/0009-embedding-model-and-llm-provider.md) if its approved
  scope requires a durable architectural decision.

## Execution Results

- Added this proposed chapter-versioning and RAG-derivation task note.
- Renumbered the existing proposed chat RAG workflow task from Task-015 to
  Task-016 to preserve sequential task numbering.
- Kept stable architecture and schema documentation unchanged apart from the
  Task-016 reference needed by the rename.

## Follow-Up

- Confirm the CMS ownership model for logical chapters and chapter revisions
  before creating Strapi content types or database migrations.
- Define the exact normalized-text contract before checksum comparison is
  implemented.
- Create a separate implementation issue once this proposed design is accepted.
