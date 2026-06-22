# Schemas

<record_type>schema_index</record_type>
<status>living</status>

## Current Schema Locations

- `tools/content-preparation/config/chapter_metadata.schema.json`
- `tools/content-preparation/config/conversion_job.schema.json`
- `apps/gurubodh-cms/src/api/**/content-types/**/schema.json`

## Ownership Guidance

- Content preparation JSON schemas belong under `tools/content-preparation/config/`.
- Strapi content type schemas belong under the relevant Strapi API directory.
- New schema locations should be added to this index when introduced.

## Change Rules

<schema_change_rules>
- Update examples, jobs, tests, or documentation when a schema change affects expected input.
- Preserve backward compatibility unless the task explicitly approves a breaking change.
- Document breaking schema changes in `docs/decisions/` or `docs/adr/` depending on impact.
</schema_change_rules>
