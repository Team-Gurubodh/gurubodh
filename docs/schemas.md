# Schemas

<record_type>schema_index</record_type>
<status>living</status>

## Current Schema Locations

- `tools/content-preparation/config/chapter_metadata.schema.json`
- `tools/content-preparation/config/conversion_job.schema.json`
- `tools/seed-data/config/category_artifact.schema.json`
- `tools/seed-data/config/glossary_artifact.schema.json`
- `tools/seed-data/config/seed_data_sources.schema.json`
- `tools/seed-data/config/subject_artifact.schema.json`
- `apps/gurubodh-cms/src/api/**/content-types/**/schema.json`

## Planned Schema Locations

None currently recorded.

## Ownership Guidance

- Content preparation JSON schemas belong under `tools/content-preparation/config/`.
- Conversion job configs support `local` and `r2` source/destination storage
  backends. R2 metadata references use bucket/key pairs and nullable URLs.
- Chapter metadata includes `integrity.artifacts.text` for the SHA-256 checksum
  of the generated chapter `.txt` artifact bytes. It does not checksum the
  metadata JSON artifact.
- Seed-data JSON schemas belong under `tools/seed-data/config/` once the
  config-driven source discovery task is implemented.
- Glossary seed-data artifacts are validated by
  `tools/seed-data/config/glossary_artifact.schema.json` before they are used by
  later ingestion tooling.
- Category seed-data artifacts are validated by
  `tools/seed-data/config/category_artifact.schema.json` before they are used by
  later ingestion tooling.
- Subject seed-data artifacts are validated by
  `tools/seed-data/config/subject_artifact.schema.json` before they are used by
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
