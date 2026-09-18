# Seed-Data Artifact Interface

<record_type>interface_contract</record_type>
<status>accepted</status>
<date>2026-07-07</date>
<owners>Gurubodh maintainers</owners>

## Purpose

This document defines the lightweight interface between externally maintained
seed-data CSV files, `tools/seed-data-cli`, generated JSON artifacts, and
Strapi 5 ingestion.

The contract exists so source data can evolve without losing the fields and
relationships required for correct CMS behavior. It is intentionally practical:
the checked-in schemas and adapters implement the supported seed-data types.

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
  sources backed by separate Strapi Collection Types, so term
  codes are not required to be globally unique across glossary sources.

## Glossary Artifact Contract

The glossary artifact contract covers:

```text
artifacts/glossary/sanatan-glossary.json
artifacts/glossary/prabodhan-glossary.json
```

Each glossary artifact represents one source glossary and one Strapi
Collection Type target. The artifact is not itself a Strapi content-type schema;
it is reviewable seed data consumed by the seed-data CLI ingestion workflow.

The glossary artifact shape uses this envelope:

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

The glossary artifact schema validates the common envelope and required common
fields and rejects additional properties. Collection-specific fields would
require a future schema change.

## Glossary Strapi Collection Type Contract

Sanatan Glossary and Prabodhan Glossary are separate Strapi 5 Collection Types
with Draft & Publish enabled and non-localized fields. Their checked-in schemas
are [Sanatan Glossary](../../apps/gurubodh-cms/src/api/sanatan-glossary/content-types/sanatan-glossary/schema.json)
and [Prabodhan Glossary](../../apps/gurubodh-cms/src/api/prabodhan-glossary/content-types/prabodhan-glossary/schema.json).

The shared Strapi-facing fields are:

- `code` - unique and required within the collection. Ingestion maps artifact
  `term_code` to this Strapi field.
- `term` - required text/string field containing the glossary term.
- `definition` - required text field containing the glossary definition.

There are no glossary relationships in the initial contract. Later work may add
collection-specific fields, especially for Prabodhan Glossary, without requiring
Sanatan Glossary to adopt the same fields.

The implemented [glossary ingestion workflow](../../tools/seed-data-cli/README.md#glossary-strapi-ingestion-workflow)
requires these Collection Types in the target CMS and provides preflight checks,
dry-run reporting, and repeatable create/update operations through the Strapi API.

## Category Artifact Contract

The category artifact contract covers:

```text
artifacts/category/categories.json
```

The category artifact represents the configured Category CSV source and the
Strapi Category Collection Type target. The artifact is reviewable seed
data consumed by the ingestion workflow; it is not a Strapi content-type
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
- `desired_status` - retained source lifecycle value, `draft` or `published`;
  current ingestion ignores it and publishes all created or updated records.
- `name_en` and `description_en` - English display text.
- `name_hi_IN` and `description_hi_IN` - Hindi display text from CSV columns
  named `name_hi-IN` and `description_hi-IN`.

The generated artifact must not include Strapi internal identifiers such as
`id`, `documentId`, internal timestamps, or created/updated user fields.

## Subject Artifact Contract

The subject artifact contract covers:

```text
artifacts/subject/subjects.json
```

The subject artifact represents the configured Subject CSV source and the
Strapi Subject Collection Type target. Subject records reference
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
- `desired_status` - retained source lifecycle value, `draft` or `published`;
  current ingestion ignores it and publishes all created or updated records.
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

Formal JSON Schemas for seed-data artifacts are checked in under
`tools/seed-data-cli/config/`:

- [Category artifact schema](../../tools/seed-data-cli/config/category_artifact.schema.json)
- [Glossary artifact schema](../../tools/seed-data-cli/config/glossary_artifact.schema.json)
- [Subject artifact schema](../../tools/seed-data-cli/config/subject_artifact.schema.json)

These schemas validate generated seed-data artifact files before ingestion and are
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

Subject validation also verifies category references against the Category source.

## Strapi Compatibility

CSV-to-JSON artifact generation targets this repo-owned interface contract.
It should not depend on a live Strapi instance, Strapi MCP server, or Strapi API
connection.

The CLI provides target-specific `ingest preflight`, `ingest plan`, and
`ingest apply` commands for Category, Subject, Sanatan Glossary, and Prabodhan
Glossary. It validates artifact schemas and target identity, checks CMS endpoint
access, and plans creates, updates, conflicts, and blocked records using stable
business keys. Adapters explicitly map artifact fields to CMS fields.

Category and Subject use separate apply invocations. Required Categories must
exist before dependent Subjects can be applied; applying Categories does not
automatically apply Subjects. Subject ingestion resolves `category_code` to a
Category `documentId` and blocks missing or ambiguous relations. Both adapters
report `desired_status` as skipped and publish records regardless of its value.
See the [Category and Subject ingestion guide](../../tools/seed-data-cli/README.md#strapi-ingestion-workflow)
for commands, locale requirements, and recovery guidance.

Strapi remains responsible for generating native `id` and Strapi 5
`documentId` values during API-based ingestion.

## Open Decisions

- Future collection-specific glossary fields beyond the initial shared
  `term_code`, `term`, and `definition` fields.
- Whether generated category, subject, and glossary artifacts should all be
  committed as reviewable project data or selectively regenerated as local
  outputs.
