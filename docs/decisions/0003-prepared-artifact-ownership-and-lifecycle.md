# Decision-0003: Prepared Artifact Ownership and Lifecycle

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-08-02</date>
<owners>Gurubodh maintainers</owners>

## Context

Prepared canonical content, derived chunks, and audit reports share a subject
tree. Deleting that tree during a prep overwrite could silently remove derived
outputs and audit evidence owned by other commands.

## Decision

`prep-subject` owns canonical proofread chapter text/metadata and the candidate
content manifest,
unmodified chapter input snapshots under `chapters/unmodified_source_text/`,
and mandatory proof-reading provenance under `chapters/proofreading/`.
The separate `generate-docx` command owns derived exports under
`chapters/msword/`; `prep-subject` may invalidate that path after canonical
replacement but never generates it. The retired `full_subject/` path has no
replacement. `generate-chunks` owns v2 candidate semantic artifacts under
`chapters/semantic_chunks/`. Their
audit reports are retained independently under
`run_reports/prep-subject/` and `run_reports/generate-chunks/`.

`prep-subject` also owns its operational state under
`run_state/prep-subject/` and its non-canonical staged workspace under
`.work/prep-subject/{job-id}/`. A durable job-state gate separates incomplete
or publishing work from canonical consumption. Only state `succeeded` with a
matching canonical content manifest authorizes `generate-chunks`.

Each ownership boundary is scoped to the language-qualified subject release
root defined by [Decision-0005](./0005-language-scoped-prepared-content-release-roots.md).
Therefore Hindi and Marathi canonical trees, checkpoints, reports, semantic
outputs, and overwrite effects are isolated even when they belong to the same
subject grouping.

The versioned text and metadata files in `chapters/text_and_metadata/` are the
proofread source of truth. The corresponding unmodified-source file is
provenance only; it never has metadata, is not manifest-listed, and cannot be a
chunking candidate. Each proof-reading details artifact binds those two text
artifacts and the locally generated whitespace-preserving diff without
embedding source/corrected text, prompts, credentials, or raw responses.

An overwrite is scoped to the command's paths. It archives its earlier state
record and discards only the associated staged workspace; it keeps the prior
canonical tree, semantic outputs, derived chapter DOCX, and legacy
`full_subject/` while the new job is incomplete. After successful canonical
replacement, same-locale `chapters/msword/`, both v2 semantic artifacts, and
the legacy `chapters/semantic_chunks_and_embeddings/` path are invalidated, with an
operator notice to regenerate derived outputs; legacy `full_subject/` is
removed. The legacy semantic path is unsupported
for new ingestion; `generate-chunks --overwrite` removes it before creating
v2 output. Local and R2 replacement are not a fully atomic multi-prefix
release; versioned releases and a current pointer are deferred.

## Rationale

Proofreading is a required staging step. All chapter responses must validate
before the proofread canonical tree and its manifest are promoted locally or
published to R2. This preserves the canonical/derived boundary and audit
history without introducing premature revision or release infrastructure.

## Impact

Operators must rerun `generate-chunks` after overwriting canonical content.
They must also rerun `generate-docx` once that command is available if chapter
DOCX exports are required. Old incomplete six-file prep checkpoints cannot
resume under the text-only five-file contract and require `--overwrite`;
already succeeded releases remain consumable by downstream commands.
They must regenerate pre-language-root Hindi artifacts into `hi-IN` explicitly;
the CLI never relocates or deletes those legacy artifacts automatically.
Future commands must declare their owned paths before implementing overwrite.

## Review Trigger

Revisit when concurrent writers, CMS ingestion, or production release recovery
requires atomic publication.
