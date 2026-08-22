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

`prep-subject` owns canonical artifacts (`full_subject/`, chapter DOCX,
chapter text/metadata, and the candidate content manifest). `generate-chunks`
owns v2 candidate semantic artifacts under `chapters/semantic_chunks/`. Their
audit reports are retained independently under
`run_reports/prep-subject/` and `run_reports/generate-chunks/`.

An overwrite is scoped to the command's paths. After successful canonical
replacement, both v2 semantic artifacts and the legacy
`chapters/semantic_chunks_and_embeddings/` path are invalidated, with an
operator notice to regenerate candidate chunks. The legacy path is unsupported
for new ingestion; `generate-chunks --overwrite` removes it before creating
v2 output. Local and R2 replacement are not a fully atomic multi-prefix
release; versioned releases and a current pointer are deferred.

## Rationale

This preserves the canonical/derived boundary and audit history without
introducing premature revision or release infrastructure.

## Impact

Operators must rerun `generate-chunks` after overwriting canonical content.
Future commands must declare their owned paths before implementing overwrite.

## Review Trigger

Revisit when concurrent writers, CMS ingestion, or production release recovery
requires atomic publication.
