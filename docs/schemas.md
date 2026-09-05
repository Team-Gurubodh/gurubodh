# Schemas

<record_type>schema_index</record_type>
<status>living</status>

## Current Schema Locations

- `tools/gurubodh-cli/config/artifacts/audit_report.schema.json`
- `tools/gurubodh-cli/config/artifacts/chapter_metadata.schema.json`
- `tools/gurubodh-cli/config/artifacts/chapter_content_manifest.schema.json`
- `tools/gurubodh-cli/config/artifacts/chapter_proofreading.schema.json`
- `tools/gurubodh-cli/config/artifacts/docx_manifest.schema.json`
- `tools/gurubodh-cli/config/artifacts/proofreading_manifest.schema.json`
- `tools/gurubodh-cli/config/artifacts/prep_subject_job_state.schema.json`
- `tools/gurubodh-cli/config/artifacts/semantic_chunks.schema.json`
- `tools/gurubodh-cli/config/artifacts/semantic_chunks_manifest.schema.json`
- `tools/gurubodh-cli/config/jobs/generate_chunks_job.schema.json`
- `tools/gurubodh-cli/config/jobs/generate_docx_job.schema.json`
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

### Gurubodh CLI runtime authority

The Gurubodh CLI executes its Draft 2020-12 job and artifact schemas at runtime.
They are not documentation-only contracts:

- `prep-subject`, `generate-chunks`, and `generate-docx` validate the parsed raw
  job JSON against the matching schema before converting it to a typed prepared
  job record or using any configuration field. Runtime-only locale, provider,
  model, and compiled-pattern values are fields on that record rather than keys
  in the schema-shaped job payload.
- Schema-governed JSON payloads are built in memory and validated before JSON
  serialization, checksum calculation, staging, local publication, or R2
  upload. This covers chapter metadata, chapter content manifests, chapter
  proofreading details, proofreading manifests, prep-subject job state,
  semantic chunks, semantic chunk manifests, DOCX manifests, and the common
  audit-report envelope.
- Audit report schema `2.0.0` is shared by `prep-subject`, `generate-chunks`,
  `generate-docx`, and lab proofreading. It fixes the common top-level
  identity, safe configuration, summary, lifecycle, publication, bounded
  failure, report-reference, and `command_details` fields while allowing each
  command to own the contents of its summary and details. The v2 major version
  is intentionally incompatible with the earlier command-specific v1 report
  layouts; retained v1 reports stay immutable, and consumers must select a
  parser by `schema_name` and the major `schema_version`.
- The validator explicitly uses JSON Schema Draft 2020-12, validates schema
  definitions before use, checks declared formats, and caches compiled
  validators. The `jsonschema` dependency and schema files are included in the
  installed CLI distribution; source-tree and container execution use the same
  files under `tools/gurubodh-cli/config/`.
- Validation failures are deterministic and identify the config/artifact,
  available file path, exact JSONPath-like location, and actionable rule. A
  normal validation failure exits without exposing raw content, credentials,
  environment values, or third-party exception dumps.

The JSON Schemas own structural rules such as object shape, required fields,
types, constants/enums, patterns, bounds, conditionals, unique arrays, and
`additionalProperties`. Python validation remains only for runtime semantics
that are not fully represented by those schemas: safe language-qualified POSIX
paths, regex compilation, locale-derived invariants, matching source and
destination release roots, artifact/checksum identity, and runtime model/cache
behavior.

The prep-subject `metadata_defaults` object retains its existing explicit
`additionalProperties: true` extension point in schema `1.5.0`; only declared
properties have schema-defined behavior today. All other strict job objects
continue to reject unknown properties. The same schema now declares
`source.file_format` as `const: "docx"`, aligning the executable contract with
the only format the maintained prep pipelines support. See
[Decision-0007](./decisions/0007-executable-cli-json-schema-boundaries.md).

- Gurubodh CLI job schemas belong under `tools/gurubodh-cli/config/jobs/`.
- Gurubodh CLI artifact schemas belong under
  `tools/gurubodh-cli/config/artifacts/`.
- Prep-subject job configs support `local` and `r2` source/destination storage
  backends. R2 metadata references use bucket/key pairs and nullable URLs.
- Prep-subject job schema `1.5.0` requires explicit `metadata_defaults.language`
  and supports only `hi-IN` and `mr-IN`. Both require
  `source_script: "Devanagari"` and `output_text_encoding: "UTF-8"`.
  Its source encoding values are `unicode` and `aps`; `shreelipi` is rejected
  as an intentional safety-boundary change recorded in
  [Decision-0006](./decisions/0006-source-font-safety-boundary.md).
  `destination.subject_dir` must be a safe nested POSIX-relative path whose
  final segment equals that language. Generate-chunks job schema `1.2.0`
  applies the same locale restriction to `naming.language` and requires source
  and destination to use the same language-qualified subject root.
  Generate-docx job schema `1.0.0` uses the same local/R2 subject-artifact
  locations and safe language-qualified root rules, but requires only the
  category, subject, title slug, and language naming identity needed for export.
- Prep-subject job `metadata_defaults.summary_chapter_markers` explicitly
  configures Devanagari search terms that add `summary_chapter` and
  `उपसंहार` to chapter metadata `content.automated_tags` when found in
  generated chapter text. If omitted, summary chapter detection is disabled for
  that job.
- Chapter metadata includes `integrity.artifacts.text` for the SHA-256 checksum
  of the generated canonical chapter `.txt` artifact bytes: UTF-8 with no CR
  bytes, LF internal line boundaries, and exactly one final LF. It does not
  checksum the metadata JSON artifact. This exact-byte integrity contract is
  distinct from content identity's v1 comparison normalization.
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
- The config-driven `generate-docx` command consumes the same exact
  `chapters/chapter_content_manifest.json` readiness set and writes
  `chapters/msword/docx_manifest.json` using schema `1.0.0`. The manifest binds
  formatting/title contract `1.0.0`, ordered canonical identities and text
  checksums, generated titles, DOCX references/checksums, and the exact source
  manifest. DOCX files are rebuildable human-readable exports, not canonical
  content and not chunking candidates.
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
  compatibility, job-level replacement authorization, lease, per-chapter state,
  artifact checksums, publication, and report references; it must never contain
  credentials, raw requests/responses, or full chapter text. Schema version `2`
  requires the boolean `replacement_authorized` field so an overwrite-authorized
  job retains that intent across `--resume`. `generate-chunks` and
  `generate-docx` require this state to be `succeeded` and to bind the published
  chapter content manifest before either command can mutate its derived output.
  Checkpoint compatibility contract version `2` validates exactly the five
  per-chapter canonical/provenance files. Old incomplete six-file checkpoints
  require a fresh `prep-subject --overwrite`; old succeeded releases remain
  downstream-consumable. Incomplete schema-version-1 checkpoints lack reliable
  replacement authorization and also require a fresh `--overwrite`; succeeded
  schema-version-1 checkpoints migrate conservatively with replacement cleanup
  disabled.
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
