# Seed-Data Artifact Interface

<record_type>interface_contract</record_type>
<status>accepted</status>
<date>2026-07-07</date>
<owners>Gurubodh maintainers</owners>

## Purpose

This document defines the lightweight interface between externally maintained
seed-data CSV files, `tools/seed-data-cli`, generated JSON artifacts, and future
Strapi 5 ingestion.

The contract exists so source data can evolve without losing the fields and
relationships required for correct CMS behavior. It is intentionally practical:
the implementation tasks may refine details as each seed-data type is built.

## Boundary

```text
Google Sheets / exported CSV files
-> tools/seed-data-cli source configuration
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

The source root and source definitions are represented in
`tools/seed-data-cli/config/seed_data_sources.json`.

## Artifact Locations

Generated JSON artifacts should be written under `tools/seed-data-cli/artifacts/`
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
- Glossary records use a stable term code within the target glossary
  collection. Sanatan Glossary and Prabodhan Glossary are separate glossary
  sources that are intended to become separate Strapi Collection Types, so term
  codes are not required to be globally unique across glossary sources.

## Glossary Artifact Contract

Task 008 finalizes the first glossary artifact contract for:

```text
artifacts/glossary/sanatan-glossary.json
artifacts/glossary/prabodhan-glossary.json
```

Each glossary artifact represents one source glossary and one intended Strapi
Collection Type target. The artifact is not itself a Strapi content-type schema;
it is reviewable seed data prepared for a later ingestion tool.

The initial glossary artifact shape should use this envelope:

```json
{
  "schema_version": 1,
  "workflow": "glossary",
  "source": {
    "key": "sanatan-glossary",
    "label": "Sanatan Glossary"
  },
  "strapi": {
    "collection_type": "sanatan-glossary",
    "display_name": "Sanatan Glossary"
  },
  "records": [
    {
      "term_code": "T00001",
      "term": "anirvachaneeya",
      "definition": "indescribable"
    }
  ]
}
```

The required common record fields are:

- `term_code` - stable business key within the target glossary collection.
- `term` - glossary term.
- `definition` - glossary definition.

The generator must not include Strapi internal identifiers such as `id`,
`documentId`, internal timestamps, or created/updated user fields. Those values
belong to Strapi and are assigned or managed during ingestion.

Sanatan Glossary and Prabodhan Glossary may diverge over time. The initial
artifact schema should validate the common envelope and required common fields,
while allowing the implementation to introduce collection-specific fields in a
future schema version or collection-specific schema if Prabodhan Glossary needs
additional properties.

## Glossary Strapi Collection Type Contract

Sanatan Glossary and Prabodhan Glossary should be modeled as separate Strapi 5
Collection Types. Task 008 records this contract but does not create the CMS
schema files.

The future CMS task should create Strapi schema files under the CMS app using
the standard Strapi content-type location:

```text
apps/gurubodh-cms/src/api/sanatan-glossary/content-types/sanatan-glossary/schema.json
apps/gurubodh-cms/src/api/prabodhan-glossary/content-types/prabodhan-glossary/schema.json
```

The initial shared Strapi-facing fields should be:

- `code` - unique and required within the collection. Ingestion maps artifact
  `term_code` to this Strapi field.
- `term` - required text/string field containing the glossary term.
- `definition` - required text field containing the glossary definition.

There are no glossary relationships in the initial contract. Later work may add
collection-specific fields, especially for Prabodhan Glossary, without requiring
Sanatan Glossary to adopt the same fields.

The later Strapi ingestion task should assume these Collection Types already
exist. It should focus on dry-run reporting, idempotent create/update behavior,
API authentication, payload construction, and conflict handling.

## Category Artifact Contract

Task 009 finalizes the category artifact contract for:

```text
artifacts/category/categories.json
```

The category artifact represents the configured Category CSV source and the
future Strapi Category Collection Type target. The artifact is reviewable seed
data prepared for a later ingestion tool; it is not a Strapi content-type
schema.

The category artifact shape uses this envelope:

```json
{
  "schema_version": 1,
  "workflow": "category",
  "source": {
    "key": "categories",
    "label": "Categories"
  },
  "strapi": {
    "collection_type": "category",
    "display_name": "Categories"
  },
  "records": [
    {
      "category_code": "CAT001",
      "legacy_code": null,
      "is_active": true,
      "sort_order": 1,
      "desired_status": "published",
      "name_en": "Tattvagyan",
      "description_en": "Tattvagyan",
      "name_hi_IN": "तत्त्वज्ञान",
      "description_hi_IN": "तत्त्वज्ञान"
    }
  ]
}
```

The required common record fields are:

- `category_code` - stable category business key.
- `legacy_code` - optional legacy reference code, represented as `null` when
  blank in CSV.
- `is_active` - parsed boolean activity flag.
- `sort_order` - parsed integer ordering value.
- `desired_status` - intended publish lifecycle value, currently `draft` or
  `published`.
- `name_en` and `description_en` - English display text.
- `name_hi_IN` and `description_hi_IN` - Hindi display text from CSV columns
  named `name_hi-IN` and `description_hi-IN`.

The generated artifact must not include Strapi internal identifiers such as
`id`, `documentId`, internal timestamps, or created/updated user fields.

## Subject Artifact Contract

Task 010 finalizes the subject artifact contract for:

```text
artifacts/subject/subjects.json
```

The subject artifact represents the configured Subject CSV source and the
future Strapi Subject Collection Type target. Subject records reference
categories by stable `category_code`; the artifact must not include Strapi
relation IDs.

The subject artifact shape uses this envelope:

```json
{
  "schema_version": 1,
  "workflow": "subject",
  "source": {
    "key": "subjects",
    "label": "Subjects"
  },
  "strapi": {
    "collection_type": "subject",
    "display_name": "Subjects"
  },
  "records": [
    {
      "subject_code": "SUB001",
      "legacy_code": null,
      "is_active": true,
      "sort_order": 1,
      "category_code": "CAT008",
      "desired_status": "published",
      "name_en": "Swasthya Rahasya",
      "description_en": "Swasthya Rahasya",
      "name_hi_IN": "स्वास्थ्य रहस्य",
      "description_hi_IN": "स्वास्थ्य रहस्य",
      "from_date": "2005-11-04",
      "to_date": "2006-01-22",
      "prabodhan_count": 24
    }
  ]
}
```

The required common record fields are:

- `subject_code` - stable subject business key.
- `legacy_code` - optional legacy reference code, represented as `null` when
  blank in CSV.
- `is_active` - parsed boolean activity flag.
- `sort_order` - parsed integer ordering value.
- `category_code` - stable category business key used for the relationship.
- `desired_status` - intended publish lifecycle value, currently `draft` or
  `published`.
- `name_en` and `description_en` - English display text.
- `name_hi_IN` and `description_hi_IN` - Hindi display text from CSV columns
  named `name_hi-IN` and `description_hi-IN`.
- `from_date` and `to_date` - optional `YYYY-MM-DD` source timeline values,
  represented as `null` when blank in CSV.
- `prabodhan_count` - optional parsed integer count, represented as `null` when
  blank in CSV.

The generated artifact must not include Strapi internal identifiers such as
`id`, `documentId`, internal timestamps, relation IDs, or created/updated user
fields.

## Artifact Schema Location

Formal JSON Schemas for seed-data artifacts belong under:

```text
tools/seed-data-cli/config/
```

The glossary artifact schema should be introduced as:

```text
tools/seed-data-cli/config/category_artifact.schema.json
tools/seed-data-cli/config/glossary_artifact.schema.json
tools/seed-data-cli/config/subject_artifact.schema.json
```

That schema validates generated seed-data artifact files before ingestion. It is
separate from the Strapi Collection Type schemas stored under
`apps/gurubodh-cms/src/api/`.

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

- Future collection-specific glossary fields beyond the initial shared
  `term_code`, `term`, and `definition` fields.
- Whether generated category, subject, and glossary artifacts should all be
  committed as reviewable project data or selectively regenerated as local
  outputs.
