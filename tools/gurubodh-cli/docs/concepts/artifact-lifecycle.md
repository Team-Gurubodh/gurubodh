# Artifact lifecycle

This page describes the contract shared by the maintained workflows. It is the authoritative home for artifact ownership and cross-command invalidation.

## Ownership and order

```text
prep-subject
  owns canonical text, metadata, source/proofreading records, prep state, and prep reports
  ├─ generate-chunks owns semantic chunks and chunk reports
  └─ generate-docx owns DOCX exports and DOCX reports
```

Each prepared release is rooted at `<subject-group>/<language>/`; `hi-IN` and `mr-IN` are independent releases. No command owns the complete subject root. `--overwrite` replaces only the invoking command's owned paths.

A successful `prep-subject --overwrite` invalidates same-locale chunks and DOCX exports because they may no longer match canonical content. Chunks and DOCX do not invalidate one another. Do not run concurrent writers for a subject and locale.

## Canonical content and integrity

The versioned canonical `.txt` under `chapters/text_and_metadata/` is the proofread source of truth. It is emitted as UTF-8 bytes with no carriage returns, LF at every internal line boundary, and exactly one final LF. Its metadata includes an exact SHA-256 of those artifact bytes and a deterministic `content_identity`. Content identity is a separate v1 comparison contract: it normalizes to NFC Unicode, LF line endings, no trailing spaces/tabs per line, and no outer Unicode whitespace. Canonical artifact formatting does not apply those additional identity transformations. Text edits create a new provenance key; reordering unchanged text does not.

`chapters/chapter_content_manifest.json` is the authoritative candidate set. Derived chunks and DOCX exports bind their outputs to it. The `semantic_chunks_manifest.json` and `docx_manifest.json` are their respective readiness markers.

## Audits and recovery

Each maintained command writes JSON and Markdown audit reports below `run_reports/<command>/`. JSON is the tooling source of truth; Markdown is the operator summary. Reports capture run identity, safe configuration/provenance, artifact summaries, and outcomes, but exclude credentials, environment values, request bodies, and full content.

Preparation checkpoint state lives at `run_state/prep-subject/job-state.json`. Use `prep-subject --resume` only for a compatible incomplete checkpoint. See [Prepare a subject](../workflows/prepare-a-subject.md) for the compatibility and replacement rules.

Derived commands retain carriage-return rejection as a defense-in-depth check.
They do not repair malformed existing releases: regenerate a canonical artifact
containing CR with an intentional `prep-subject --overwrite` before deriving
chunks or DOCX.
