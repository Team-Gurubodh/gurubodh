# Seed-Data Artifact Interface

<record_type>interface_contract</record_type>
<status>proposed</status>
<date>2026-07-07</date>
<owners>Gurubodh maintainers</owners>

## Purpose

This document defines the lightweight interface between externally maintained
seed-data CSV files, `tools/seed-data`, generated JSON artifacts, and future
Strapi 5 ingestion.

The contract exists so source data can evolve without losing the fields and
relationships required for correct CMS behavior. It is intentionally practical:
the implementation tasks may refine details as each seed-data type is built.

## Boundary

```text
Google Sheets / exported CSV files
-> tools/seed-data source configuration
-> validated JSON artifacts
-> Strapi 5 content types and API ingestion
```

CSV-to-JSON generation must be deterministic and should not require a running
Strapi instance. Strapi schema/API compatibility checks belong to the ingestion
stage or an explicit dry-run compatibility command.

## Supported Seed-Data Types

- `glossary` - glossary terms maintained as separate source glossaries.
- `category` - category records used to group subjects.
- `subject` - subject records that reference categories.

## Source Locations

The external CSV source root is:

```text
/Users/rajeev/Gurubodh_library/seed_data/csv_import
```

Expected source paths are relative to that root:

```text
category/categories.csv
glossary/sanatan-glossary.csv
glossary/prabodhan-glossary.csv
subject/subjects.csv
```

The source root and source definitions should be represented in
`tools/seed-data/config/seed_data_sources.json` after the config-driven
foundation task is implemented.

## Artifact Locations

Generated JSON artifacts should be written under `tools/seed-data/artifacts/`
using stable workflow directories:

```text
artifacts/category/categories.json
artifacts/glossary/sanatan-glossary.json
artifacts/glossary/prabodhan-glossary.json
artifacts/subject/subjects.json
```

Artifacts are reviewable staging outputs. They must not contain Strapi internal
identifiers such as `id`, `documentId`, internal timestamps, or created/updated
user fields.

## Stable Keys

Seed-data reconciliation must use stable business keys rather than Strapi
internal identifiers.

- Category records use a stable category code.
- Subject records use a stable subject code and reference category by category
  code.
- Glossary records use a stable term code. If term codes are not globally
  unique across glossary sources, ingestion must use a documented composite key
  of glossary source plus term code.

## Validation Responsibilities

The seed-data tool must validate CSV source files before writing JSON artifacts.
Spreadsheet validations are entry-time guidance only and do not replace tooling
validation.

Common validation responsibilities include:

- required headers are present in the expected order unless a task explicitly
  decides otherwise;
- required values are present;
- stable keys match the expected format;
- duplicate stable keys are rejected within the relevant source scope;
- generated artifacts are not written when validation reports errors;
- validation messages identify the source row and field wherever practical.

Subject validation must also verify category references once category artifacts
or source records are available.

## Strapi Compatibility

CSV-to-JSON artifact generation targets this repo-owned interface contract.
It should not depend on a live Strapi instance, Strapi MCP server, or Strapi API
connection.

Future Strapi ingestion or dry-run compatibility checks should compare generated
artifacts with Strapi expectations:

- missing required Strapi field: error;
- unresolved relationship: error;
- target Strapi content type missing: error;
- artifact field missing in Strapi: warning or blocked change, depending on
  whether the field is intentionally new;
- optional Strapi field missing in artifact: warning;
- existing record with changed updateable field: planned update in dry-run.

Strapi remains responsible for generating native `id` and Strapi 5
`documentId` values during API-based ingestion.

## Open Decisions

- Final Strapi content-type field names for category, subject, and glossary
  records.
- Whether glossary term code is globally unique or scoped by glossary source.
- Exact generated JSON shape for each seed-data type.
- Whether generated artifacts should eventually be committed or remain ignored
  regenerated outputs.
