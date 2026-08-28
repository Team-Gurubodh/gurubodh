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

A successful `prep-subject --overwrite` invalidates same-locale chunks and DOCX exports because they may no longer match canonical content. Chunks and DOCX do not invalidate one another. `prep-subject` is single-writer per destination; its local advisory lock and R2 advisory lease are guardrails rather than reliable mutual exclusion, so concurrent writers can duplicate Gemini calls and overwrite checkpoint/workspace artifacts.

## Canonical content and integrity

The versioned canonical `.txt` under `chapters/text_and_metadata/` is the proofread source of truth. It is emitted as UTF-8 bytes with no carriage returns, LF at every internal line boundary, and exactly one final LF. Its metadata includes an exact SHA-256 of those artifact bytes and a deterministic `content_identity`. Content identity is a separate v1 comparison contract: it normalizes to NFC Unicode, LF line endings, no trailing spaces/tabs per line, and no outer Unicode whitespace. Canonical artifact formatting does not apply those additional identity transformations. Text edits create a new provenance key; reordering unchanged text does not.

`chapters/chapter_content_manifest.json` is the authoritative candidate set. Derived chunks and DOCX exports bind their outputs to it. The `semantic_chunks_manifest.json` and `docx_manifest.json` are their respective readiness markers.

## Shared derived-publication lifecycle

`generate-chunks` and `generate-docx` use the same staged-publication state machine:

1. `preflight` inspects command-owned destinations and requires `--overwrite` when needed, without modifying output.
2. `source_validation` materializes and validates the candidate canonical release.
3. `generation` writes only into a unique staged workspace.
4. `staged_validation` writes the command readiness manifest and validates it with every staged artifact.
5. `source_revalidation` verifies immediately before publication that the canonical release is still the candidate release.
6. `publication` invokes the local or R2 strategy.
7. `success_audit` records the actual publication result.

An exception or interruption in any state attempts a durable failure audit without masking the original error. The audit records the failing state, bounded error details, known prior/publication state, and per-chapter progress. A failure before successful local publication leaves a prior derived-output set intact.

Local publication copies the complete stage to a same-directory incoming path, moves the prior command-owned directory to a backup, promotes incoming output, and restores the backup if promotion fails. It never replaces a subject root or another command's output. The chunks legacy combined-output location is inspected at preflight but cleaned only after successful v2 publication; its outcome is audited.

R2 publication is readiness-based and is not atomic. On overwrite, the command removes its old readiness manifest before deleting/replacing its owned objects, uploads validated artifacts, and uploads the new readiness manifest last. Upload failure removes the readiness manifest so consumers cannot mistake a partial prefix for a ready set. Audit reports publish after the readiness manifest on success and are attempted on failure. Versioned releases and a current pointer remain outside the current contract.

## Audits and recovery

Each maintained command writes JSON and Markdown audit reports below `run_reports/<command>/`. JSON is the tooling source of truth; Markdown is the operator summary. Reports capture run identity, lifecycle transitions, safe configuration/provenance, artifact summaries, publication deletes/uploads/readiness status, and outcomes, but exclude credentials, environment values, request bodies, and full content.

Preparation checkpoint state lives at `run_state/prep-subject/job-state.json`. Use `prep-subject --resume` only for a compatible incomplete checkpoint. See [Prepare a subject](../workflows/prepare-a-subject.md) for the compatibility and replacement rules.

Derived commands retain carriage-return rejection as a defense-in-depth check.
They do not repair malformed existing releases: regenerate a canonical artifact
containing CR with an intentional `prep-subject --overwrite` before deriving
chunks or DOCX.
