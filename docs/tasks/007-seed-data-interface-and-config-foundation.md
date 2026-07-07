# Task-007: Seed-Data Interface and Config Foundation

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-07-07</date>
<owners>Gurubodh maintainers</owners>

## Goal

Establish the shared seed-data interface contract and common tooling foundation
for config-driven source discovery across `glossary`, `category`, and
`subject` seed-data workflows.

## Context

Task 006 began as glossary maintenance, but the seed-data scope now includes
three externally maintained CSV source types that will become Strapi 5 content
types or Strapi-facing reference data:

- `glossary`
- `category`
- `subject`

The CSV source files live outside the repository under:

```text
/Users/rajeev/Gurubodh_library/seed_data/csv_import
```

`tools/seed-data` currently hardcodes some source and path details in Python.
The next implementation should move those details into JSON configuration and
use a lightweight interface document to define the CSV-to-artifact boundary.

## Decisions

- Keep `tools/seed-data` as the canonical seed-data preparation and ingestion
  tooling boundary.
- Introduce `docs/interfaces/seed-data-artifacts.md` before implementing the
  next artifact-generation slices.
- Keep CSV-to-JSON artifact generation deterministic and offline.
- Do not require Strapi MCP, Strapi API access, or a running Strapi instance for
  artifact generation.
- Reserve Strapi schema/API comparison for the later ingestion or dry-run
  compatibility task.
- Represent source definitions in JSON config under `tools/seed-data/config/`.

## Approved Plan

1. Close the superseded glossary-only planning records.
   - Mark `docs/tasks/006-glossary-maintenance.md` as `closed-superseded`.
   - Close GitHub issue #11 as superseded by this seed-data task series.

2. Add the seed-data interface document.
   - Create `docs/interfaces/seed-data-artifacts.md`.
   - Define the boundary from CSV source files to config, JSON artifacts, and
     later Strapi ingestion.
   - Record common validation, stable-key, artifact, and Strapi compatibility
     expectations.

3. Add seed-data source configuration.
   - Create `tools/seed-data/config/seed_data_sources.json`.
   - Include source root, artifact root, supported workflows, and source
     records for category, subject, and glossary.
   - Keep paths relative to the configured external source root or artifact
     root.

4. Add a seed-data source configuration schema.
   - Create `tools/seed-data/config/seed_data_sources.schema.json`.
   - Require schema version, source root, artifact root, workflow definitions,
     source keys, labels, CSV paths, and artifact paths.

5. Implement common config and path helpers.
   - Add or update Python modules so CLI commands can load source definitions
     from config.
   - Preserve existing CLI behavior where practical.
   - Keep the first common layer small and driven by the immediate workflows.

6. Update documentation indexes.
   - Make `docs/interfaces/` discoverable from `docs/README.md`.
   - Register the planned seed-data schema location in `docs/schemas.md`, then
     move it to current schema locations when the schema file is implemented.
   - Update `tools/seed-data/README.md` to describe the external CSV source
     root and config-driven direction.

## Execution Results

Pending.

## Follow-Up

- Task 008 will implement glossary config-driven JSON artifact generation.
- Task 009 will implement category CSV validation and JSON artifact generation.
- Task 010 will implement subject CSV validation and JSON artifact generation.
- Task 011 will implement Strapi 5 ingestion and compatibility checks.
