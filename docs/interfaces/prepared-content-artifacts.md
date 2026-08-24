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

Prepared artifact grouping is preserved as object-key prefixes:

```text
cms_library/{subject_dir}/full_subject/
cms_library/{subject_dir}/chapters/msword/
cms_library/{subject_dir}/chapters/text_and_metadata/
cms_library/{subject_dir}/chapters/chapter_content_manifest.json
cms_library/{subject_dir}/chapters/proofreading/
```

R2 prefixes are object-key strings, not real folders.

## Optional Proof-reading Review Artifacts

When a prep-subject job enables Gemini proof-reading, it writes review-only
sidecars under `chapters/proofreading/`: a corrected text copy, local
word-level diff, structured Gemini change list, and a proof-reading manifest.
Each sidecar binds to the canonical source text checksum and content identity.

These artifacts are not canonical prepared text. They are never included in
`chapter_content_manifest.json`, and `generate-chunks` must ignore them. The
canonical chapter text, chapter metadata, and content manifest remain unchanged.

## Metadata References

Chapter metadata includes storage references for the source object and each
chapter/full-subject artifact.

R2 references use:

```json
{
  "backend": "r2",
  "bucket": "gurubodh-library-dev",
  "key": "cms_library/129_spand_rahasya/chapters/text_and_metadata/example.json",
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

Every newly prepared chapter metadata artifact carries `content_identity`. Its
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

The preparation tool does not archive existing output. If output already exists,
jobs fail unless `--overwrite` is supplied. For R2 destinations, existing object
keys are checked before upload and object replacement requires `--overwrite`.
R2 jobs also check the destination subject prefix before local processing starts
so a missing overwrite flag fails early instead of after artifact generation.
