# Schemas

<record_type>schema_index</record_type>
<status>living</status>

## Current Schema Locations

- `tools/gurubodh-cli/config/artifacts/chapter_metadata.schema.json`
- `tools/gurubodh-cli/config/artifacts/chapter_content_manifest.schema.json`
- `tools/gurubodh-cli/config/artifacts/chapter_proofreading.schema.json`
- `tools/gurubodh-cli/config/artifacts/proofreading_manifest.schema.json`
- `tools/gurubodh-cli/config/artifacts/prep_subject_job_state.schema.json`
- `tools/gurubodh-cli/config/artifacts/semantic_chunks.schema.json`
- `tools/gurubodh-cli/config/artifacts/semantic_chunks_manifest.schema.json`
- `tools/gurubodh-cli/config/jobs/generate_chunks_job.schema.json`
- `tools/gurubodh-cli/config/jobs/prep_subject_job.schema.json`
- `tools/seed-data-cli/config/category_artifact.schema.json`
- `tools/seed-data-cli/config/glossary_artifact.schema.json`
- `tools/seed-data-cli/config/seed_data_sources.schema.json`
- `tools/seed-data-cli/config/subject_artifact.schema.json`
- `apps/gurubodh-cms/src/api/**/content-types/**/schema.json`

## Planned Schema Locations

- `tools/gurubodh-cli/config/artifacts/embedding_manifest.schema.json`
- `tools/gurubodh-cli/config/jobs/generate_embeddings_job.schema.json`

## Ownership Guidance

- Gurubodh CLI job schemas belong under `tools/gurubodh-cli/config/jobs/`.
- Gurubodh CLI artifact schemas belong under
  `tools/gurubodh-cli/config/artifacts/`.
- Prep-subject job configs support `local` and `r2` source/destination storage
  backends. R2 metadata references use bucket/key pairs and nullable URLs.
- Prep-subject job schema `1.4.0` requires explicit `metadata_defaults.language`
  and supports only `hi-IN` and `mr-IN`. Both require
  `source_script: "Devanagari"` and `output_text_encoding: "UTF-8"`.
  `destination.subject_dir` must be a safe nested POSIX-relative path whose
  final segment equals that language. Generate-chunks job schema `1.1.0`
  applies the same locale restriction to `naming.language` and requires source
  and destination to use the same language-qualified subject root.
- Prep-subject job `metadata_defaults.summary_chapter_markers` explicitly
  configures Devanagari search terms that add `summary_chapter` and
  `उपसंहार` to chapter metadata `content.automated_tags` when found in
  generated chapter text. If omitted, summary chapter detection is disabled for
  that job.
- Chapter metadata includes `integrity.artifacts.text` for the SHA-256 checksum
  of the generated chapter `.txt` artifact bytes. It does not checksum the
  metadata JSON artifact.
- Chapter metadata schema `1.4.0` contains only canonical metadata/text names
  in `files` and only canonical metadata/text references in
  `storage.artifacts`. DOCX and full-subject fields from schema `1.3.0` are not
  emitted as null or dangling references.
- Chapter metadata also includes `content_identity`: a UUID v5 provenance key
  and normalized-content SHA-256 for the exact normalized chapter text within
  its category, subject, and language. This does not identify an editorial
  chapter across text changes. `chapters/chapter_content_manifest.json` lists the current
  generated subject chapter set and uses the content-manifest artifact schema.
- The config-driven `generate-chunks` command consumes
  `chapters/chapter_content_manifest.json` as its authoritative candidate set
  and writes v2 per-chapter semantic chunk JSON artifacts under
  `chapters/semantic_chunks/`. They bind to the exact source candidate manifest,
  retain chunking and token-counting provenance, and contain no retrieval
  vectors. The legacy `semantic_chunks_and_embeddings` path is unsupported for
  new output and is removed only with explicit overwrite.
- Every prep-subject job requires strict Gemini proofreading. The canonical
  versioned chapter text and matching metadata under
  `chapters/text_and_metadata/` are derived from Gemini's corrected text.
  `chapters/unmodified_source_text/` retains the exact submitted source text
  without a metadata JSON; `chapters/proofreading/` holds its local diff and
  provenance details. Only the proofread canonical pair is referenced by the
  chapter content manifest or eligible for `generate-chunks`.
- Proofreading details and aggregate proofreading manifests use schema version
  `2` to record the selected locale plus a stable instruction-template ID,
  version, and SHA-256 hash. They never store the template text itself.
  Checkpoint compatibility includes this safe template provenance, so a
  template change requires a fresh overwrite rather than mixing resumed
  artifacts.
- `prep_subject_job_state.schema.json` defines the durable operational
  checkpoint at `run_state/prep-subject/job-state.json`. It records safe
  compatibility, lease, per-chapter state, artifact checksums, publication, and
  report references; it must never contain credentials, raw requests/responses,
  or full chapter text. `generate-chunks` requires this state to be `succeeded`
  and to bind the published chapter content manifest before it can mutate chunk
  output.
  Checkpoint compatibility contract version `2` validates exactly the five
  per-chapter canonical/provenance files. Old incomplete six-file checkpoints
  require a fresh `prep-subject --overwrite`; old succeeded releases remain
  downstream-consumable.
- Seed-data JSON schemas belong under `tools/seed-data-cli/config/` once the
  config-driven source discovery task is implemented.
- Glossary seed-data artifacts are validated by
  `tools/seed-data-cli/config/glossary_artifact.schema.json` before they are used by
  later ingestion tooling.
- Category seed-data artifacts are validated by
  `tools/seed-data-cli/config/category_artifact.schema.json` before they are used by
  later ingestion tooling.
- Subject seed-data artifacts are validated by
  `tools/seed-data-cli/config/subject_artifact.schema.json` before they are used by
  later ingestion tooling.
- Strapi content type schemas belong under the relevant Strapi API directory.
- Sanatan Glossary and Prabodhan Glossary Strapi content types store glossary
  `code`, `term`, and `definition` fields as non-localized fields and use
  Draft & Publish.
- New schema locations should be added to this index when introduced.

## Change Rules

<schema_change_rules>
- Update examples, jobs, tests, or documentation when a schema change affects expected input.
- Preserve backward compatibility unless the task explicitly approves a breaking change.
- Document breaking schema changes in `docs/decisions/` or `docs/adr/` depending on impact.
</schema_change_rules>
