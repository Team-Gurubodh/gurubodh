# Prepared Content Artifact Interface

<record_type>interface_contract</record_type>
<status>accepted</status>
<date>2026-07-08</date>
<owners>Gurubodh maintainers</owners>

## Purpose

This document defines the handoff contract for artifacts produced by
`tools/gurubodh-cli` and consumed later by content ingestion, metadata
generation, metadata ingestion, and CMS-backed application workflows.

## Boundary

```text
Source DOCX storage
-> tools/gurubodh-cli
-> prepared artifact storage
-> future ingestion and metadata workflows
```

Preparation may use temporary local files internally. Temporary paths must not
appear in generated metadata for R2-backed jobs.

## Storage Backends

Supported backends:

- `local` - development and compatibility filesystem storage.
- `r2` - Cloudflare R2 object storage using the S3-compatible API.

For R2, the development bucket is:

```text
gurubodh-library-dev
```

Source DOCX objects are expected under:

```text
source_library/
```

Prepared CMS-library artifacts are expected under:

```text
cms_library/
```

## Artifact Layout

Prepared artifact grouping is preserved beneath a language-specific release
root. Initially supported locales are `hi-IN` and `mr-IN`; `{language}` is the
final segment of a validated `subject_dir` and `{subject-group}` remains visible
above it.

```text
cms_library/{subject-group}/{language}/full_subject/
cms_library/{subject-group}/{language}/chapters/msword/
cms_library/{subject-group}/{language}/chapters/text_and_metadata/
cms_library/{subject-group}/{language}/chapters/unmodified_source_text/
cms_library/{subject-group}/{language}/chapters/chapter_content_manifest.json
cms_library/{subject-group}/{language}/chapters/proofreading/
cms_library/{subject-group}/{language}/run_state/prep-subject/job-state.json
cms_library/{subject-group}/{language}/.work/prep-subject/{job-id}/
```

R2 prefixes are object-key strings, not real folders.

`subject_dir` must be a safe nested POSIX-relative path: it cannot be absolute,
contain empty segments, `.`, `..`, or backslashes, and its final segment must
equal the configured language. Prep-subject uses
`metadata_defaults.language`; generate-chunks requires the same language in
its naming, source root, destination root, prepared manifest, and candidate
metadata. These roots are independent preparation and chunking release units.

## Prep-subject operational checkpoint

`run_state/prep-subject/job-state.json` is the durable operational record for a
preparation job, not a canonical content artifact. Its schema is
`prep_subject_job_state.schema.json`. It records a unique job ID, lifecycle
state, lease heartbeat, compatibility fingerprint, source checksum, bounded
per-chapter outcomes, checksum-validated staged artifact references, canonical
manifest binding, and immutable run-report references. It never contains API
keys, request/response bodies, full chapter text, or unbounded provider errors.

The job workspace is under `.work/prep-subject/{job-id}/`. It contains staged
artifacts only and is never a source for ingestion or chunk generation. Local
workspaces are retained for incomplete or publishing recovery and removed after
successful canonical promotion. R2 stores the equivalent workspace object
prefix; its multi-object publication remains recoverable but non-atomic.

The lifecycle is `running`, `incomplete`, `ready_to_publish`, `publishing`,
`succeeded`, or `failed`. Chapters are only `pending`, `failed`, or
`succeeded`. A successful chapter is reusable only after its complete staged
artifact set passes checksum validation. `generate-chunks` refuses any state
other than `succeeded`, including before an overwrite can delete chunk output.

## Mandatory Canonical Gemini Proofreading

Every `prep-subject` job must provide a strict `proofreading` object and read
its credential only from `GEMINI_API_KEY`. For every successfully prepared
chapter, preparation writes these five files across three directories:

```text
chapters/text_and_metadata/<chapter>.txt
chapters/text_and_metadata/<chapter>.json
chapters/unmodified_source_text/<chapter>_unmodified_source.txt
chapters/proofreading/<chapter>.proofread.diff.txt
chapters/proofreading/<chapter>.proofread.json
```

The versioned `.txt` and `.json` under `text_and_metadata/` are the canonical
proofread text and proofread-derived metadata. The unmodified source text is
the exact converted/extracted input submitted to Gemini; it is provenance only
and has no metadata JSON. The proof-reading details JSON binds the unmodified
and canonical text artifacts with storage references, checksums, content
identities, provider/model provenance, selected language, a stable
instruction-template ID/version/hash, request pacing/usage, local diff summary,
and Gemini edit explanations. It contains no full source/corrected text,
prompts, API keys, or raw responses.

`chapters/proofreading/proofreading_manifest.json` remains an aggregate
operational provenance artifact. It is not part of the five per-chapter files.

`chapter_content_manifest.json` lists only the proofread versioned text and
matching metadata. `generate-chunks` consumes those manifest-listed artifacts
only, so it ignores both `unmodified_source_text/` and `proofreading/`.

## Metadata References

Chapter metadata includes storage references for the source object and each
chapter/full-subject artifact.

R2 references use:

```json
{
  "backend": "r2",
  "bucket": "gurubodh-library-dev",
  "key": "cms_library/129_spand_rahasya/hi-IN/chapters/text_and_metadata/example.json",
  "url": null
}
```

Local references use:

```json
{
  "backend": "local",
  "path": "chapters/text_and_metadata/example.json",
  "url": null
}
```

URL values are optional in job configuration and nullable in generated metadata.
Consumers must treat bucket/key or local path references as canonical.

## Content Identity and Manifest

Every newly prepared canonical chapter metadata artifact carries `content_identity`. Its
`content_key` is a deterministic UUID v5 for the normalized chapter text within
the category, subject, and language. It is provenance for an exact content
state, not a stable editorial chapter identity: a text edit changes it, while
moving unchanged text to another generated chapter position does not.
The immutable Gurubodh namespace for identity contract v1 is
`7ecde8b9-3560-426a-9fd5-52bff1b6c575`.

Normalization v1 applies NFC Unicode normalization, converts CRLF/lone CR to
LF, removes trailing spaces/tabs from each line, and removes outer Unicode
whitespace. It preserves internal whitespace, paragraph boundaries,
punctuation, and other characters. The `normalized_content_sha256` is computed
from the resulting UTF-8 text without an added final newline. This is distinct
from `integrity.artifacts.text`, which checks the exact emitted `.txt` bytes.

`chapters/chapter_content_manifest.json` is a deterministic list of the current generated
chapter content keys and their metadata/text references. It does not retain
history or create a chapter registry. Existing prepared trees must be fully
regenerated with `gurubodh prep-subject --overwrite` before `generate-chunks`;
the chunk command refuses metadata without valid content identity.

## Candidate Semantic Chunks

`generate-chunks` consumes the candidate manifest as its only
chapter-selection authority. It validates selected manifest references against
chapter metadata and text before model initialization, then writes schema-v2
artifacts under `chapters/semantic_chunks/`.

Every chunk artifact and `semantic_chunks_manifest.json` records the SHA-256
of the exact UTF-8 candidate manifest bytes used for the run. Chunk artifacts
contain ordered text, spans, checksums, token estimates, and chunking
provenance only. Temporary contextual vectors may be used to determine
boundaries, but retrieval vectors are not preparation artifacts and are not
stored in local artifact trees or R2.

`chapters/semantic_chunks_and_embeddings/` is a legacy combined-output path.
It is unsupported for new ingestion. `generate-chunks` fails when it exists
unless `--overwrite` is supplied, which removes that legacy command-owned
output before producing v2 chunks.

## Overwrite Behavior

Without a flag, an incomplete checkpoint causes `prep-subject` to stop with
instructions to use `--resume` or `--overwrite`. `--resume` requires the same
source/configuration fingerprint and retries only pending or failed chapters;
on a succeeded job it exits without Gemini calls. `--resume` and `--overwrite`
are mutually exclusive. `--overwrite` archives the old state record, discards
its staged workspace, and starts a fresh job; it does not resume.

All required proofreading must succeed in staging before canonical promotion.
An unfinished overwrite leaves the previous canonical tree and its semantic
chunks intact. Only a successful replacement invalidates semantic output.
There must be no concurrent writer for a subject: local jobs take an exclusive
lock and R2 jobs use the active lease/heartbeat in job state. A stale lease is
recoverable with `--resume`.
