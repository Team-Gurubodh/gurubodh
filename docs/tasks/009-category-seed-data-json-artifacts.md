# Task-009: Category Seed-Data JSON Artifacts

<record_type>task_history</record_type>
<status>completed</status>
<date>2026-07-07</date>
<owners>Gurubodh maintainers</owners>
<github_issue>https://github.com/Team-Gurubodh/gurubodh/issues/45</github_issue>

## Goal

Validate category CSV seed data and generate a reviewable JSON artifact for
later Strapi 5 ingestion, using the same offline artifact-generation boundary
established by Task 008 for glossary seed data.

## Context

Category seed data is one of the three currently available CSV source types.
It should be implemented before subject seed data because subjects reference
categories.

Task 008 finalized the first implemented seed-data artifact workflow for
glossary sources. Category artifact generation should follow that pattern:
read configured CSV source data, validate it, generate a deterministic JSON
artifact, validate the generated artifact against a repo-owned JSON Schema, and
write the artifact only after all validation passes.

This task should stop at the seed-data artifact boundary. It should not create
or compare Strapi 5 content-type schemas, and it should not ingest records into
Strapi. Those concerns belong to later CMS/schema compatibility and ingestion
tasks.

The expected external CSV source path is:

```text
category/categories.csv
```

relative to:

```text
/Users/rajeev/Gurubodh_library/seed_data/csv_import
```

## Decisions

- Use the Task 007 config-driven source discovery foundation.
- Use Task 008 as the implementation guide for offline CSV-to-JSON artifact
  generation.
- Validate category source data before writing JSON artifacts.
- Abort artifact generation when validation reports errors.
- Treat the category code as the stable business key.
- Include category source identity in the generated artifact.
- Keep generated artifacts free of Strapi internal identifiers.
- Keep Strapi content-type creation, Strapi schema comparison, and Strapi
  compatibility checks out of this task.
- Keep actual Strapi ingestion out of this task.
- Define a formal category artifact JSON Schema under:
  - `tools/seed-data/config/category_artifact.schema.json`
- Record the durable category artifact contract in:
  - `docs/interfaces/seed-data-artifacts.md`
- Treat the generated category artifact as reviewable project data, consistent
  with the Task 008 glossary artifact decision.

## Approved Plan

1. Define required category CSV headers based on the current source file and
   seed-data artifact contract.
   - Expected source columns are currently defined by the Category Google Sheets
     setup script:
     `code`, `legacy_code`, `is_active`, `sort_order`, `desired_status`,
     `name_en`, `description_en`, `name_hi-IN`, and `description_hi-IN`.
   - Confirm the actual downloaded CSV headers before implementation and update
     this task if the source shape has changed.
2. Add category source lookup and path display through the shared config layer,
   preserving the `seed_data_sources.json` source definition for:
   - `categories`
3. Add category CSV validation for:
   - required headers in expected order;
   - required values;
   - `code` format, expected as `CATnnn`;
   - duplicate category codes;
   - duplicate non-empty `legacy_code` values;
   - duplicate `sort_order` values;
   - boolean parsing for `is_active`;
   - integer parsing for `sort_order`;
   - allowed `desired_status` values, expected as `draft` or `published`;
   - maximum length rules that mirror the seed-data source contract;
   - malformed rows and blank rows.
4. Define the category artifact shape using the same envelope style established
   by Task 008:
   - `schema_version`
   - `workflow`
   - `source`
   - `strapi`
   - `records`
5. Add a formal category artifact JSON Schema:
   - `tools/seed-data/config/category_artifact.schema.json`
6. Validate generated category artifacts against the category artifact schema.
7. Generate:
   - `tools/seed-data/artifacts/category/categories.json`
8. Ensure artifact generation runs CSV validation first and does not write an
   artifact when CSV validation or artifact validation fails.
9. Add tests for category source lookup, path display, CSV validation, artifact
   generation, and artifact-schema validation.
10. Update `docs/interfaces/seed-data-artifacts.md` with the finalized category
   artifact contract.
11. Update `tools/seed-data/README.md` with category validation and generation
   commands.

## Out of Scope

- Creating or modifying Strapi 5 category content-type schema files.
- Comparing `category_artifact.schema.json` with the Strapi category schema.
- Running Strapi compatibility checks.
- Ingesting category records into Strapi.
- Dropping, recreating, or migrating any Strapi content type.

## Execution Results

### State Summary - 2026-07-10

#### What Was Built

- Created GitHub issue #45 for the combined Task 009 and Task 010
  implementation slice.
- Created branch `issue-45-category-subject-seed-artifacts`.
- Confirmed the downloaded Category CSV headers match the expected task shape:
  - `code`, `legacy_code`, `is_active`, `sort_order`, `desired_status`,
    `name_en`, `description_en`, `name_hi-IN`, and `description_hi-IN`.
- Added Category source helpers, path display support, CSV validation, artifact
  generation, and artifact-schema validation.
- Added a formal Category artifact schema:
  - `tools/seed-data/config/category_artifact.schema.json`
- Generated the reviewable Category artifact:
  - `tools/seed-data/artifacts/category/categories.json`
- Updated `docs/interfaces/seed-data-artifacts.md` with the durable Category
  artifact contract.
- Updated `tools/seed-data/README.md` with Category validation and generation
  commands.

#### What Works

- `gurubodh-seed-data category validate --source categories` validates the
  configured Category CSV with 11 data rows.
- `gurubodh-seed-data category generate --source categories` validates the CSV,
  validates the generated artifact against the Category artifact schema, and
  writes 11 records.
- Artifact generation aborts before writing when CSV validation fails.
- Generated records include stable `category_code` values and exclude Strapi
  internal identifiers.

#### Verification

- `tools/seed-data/.venv/bin/python -m unittest discover -s tools/seed-data/tests`
- `tools/seed-data/.venv/bin/gurubodh-seed-data category validate --source categories`
- `tools/seed-data/.venv/bin/gurubodh-seed-data category generate --source categories`
- `python3 -m json.tool tools/seed-data/config/category_artifact.schema.json`
- `python3 -m json.tool tools/seed-data/artifacts/category/categories.json`

## Follow-Up

- Subject validation and artifact generation in Task 010 should validate
  subject category references against category stable keys from category source
  data or the generated category artifact.
- Later Strapi schema compatibility and ingestion tasks should decide how to
  compare category artifacts with the Strapi 5 category Collection Type.
