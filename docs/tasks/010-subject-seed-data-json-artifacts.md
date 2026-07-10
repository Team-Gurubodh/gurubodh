# Task-010: Subject Seed-Data JSON Artifacts

<record_type>task_history</record_type>
<status>completed</status>
<date>2026-07-07</date>
<owners>Gurubodh maintainers</owners>
<github_issue>https://github.com/Team-Gurubodh/gurubodh/issues/45</github_issue>

## Goal

Validate subject CSV seed data, verify subject-to-category references, and
generate a reviewable JSON artifact for later Strapi 5 ingestion, using the
same offline artifact-generation boundary established by Task 008 for glossary
seed data.

## Context

Subject seed data depends on category seed data because each subject belongs to
or references a category. This task should follow category artifact generation.

Task 008 finalized the first implemented seed-data artifact workflow for
glossary sources. Subject artifact generation should follow that pattern:
read configured CSV source data, validate it, verify cross-source references,
generate a deterministic JSON artifact, validate the generated artifact against
a repo-owned JSON Schema, and write the artifact only after all validation
passes.

This task should stop at the seed-data artifact boundary. It should not create
or compare Strapi 5 content-type schemas, and it should not ingest records into
Strapi. Those concerns belong to later CMS/schema compatibility and ingestion
tasks.

The expected external CSV source path is:

```text
subject/subjects.csv
```

relative to:

```text
/Users/rajeev/Gurubodh_library/seed_data/csv_import
```

## Decisions

- Use the Task 007 config-driven source discovery foundation.
- Use Task 008 as the implementation guide for offline CSV-to-JSON artifact
  generation.
- Treat the subject code as the stable business key.
- Validate category references by stable category code.
- Run validation before writing any generated artifact.
- Abort artifact generation when validation reports errors.
- Include subject source identity in the generated artifact.
- Keep generated artifacts free of Strapi internal identifiers.
- Keep Strapi content-type creation, Strapi schema comparison, and Strapi
  compatibility checks out of this task.
- Keep actual Strapi ingestion out of this task.
- Define a formal subject artifact JSON Schema under:
  - `tools/seed-data/config/subject_artifact.schema.json`
- Record the durable subject artifact contract in:
  - `docs/interfaces/seed-data-artifacts.md`
- Treat the generated subject artifact as reviewable project data, consistent
  with the Task 008 glossary artifact decision.

## Approved Plan

1. Define required subject CSV headers based on the current source file and
   seed-data artifact contract.
   - The Subject Google Sheets setup script uses helper columns
     `category_name_en` and `category_name_hi-IN` to populate `category_code`.
   - The actual downloaded CSV headers confirmed before implementation are:
     `code`, `legacy_code`, `is_active`, `sort_order`, `category_code`,
     `desired_status`, `name_en`, `description_en`, `name_hi-IN`,
     `description_hi-IN`, `from_date`, `to_date`, and `prabodhan_count`.
2. Add subject source lookup and path display through the shared config layer,
   preserving the `seed_data_sources.json` source definition for:
   - `subjects`
3. Add subject CSV validation for:
   - required headers in expected order;
   - required values;
   - `code` format, expected as `SUBnnn`;
   - duplicate subject codes;
   - duplicate non-empty `legacy_code` values;
   - duplicate `sort_order` values;
   - boolean parsing for `is_active`;
   - integer parsing for `sort_order`;
   - allowed `desired_status` values, expected as `draft` or `published`;
   - required `category_code`;
   - maximum length rules that mirror the seed-data source contract;
   - malformed rows and blank rows.
4. Validate subject category references against category stable keys from
   category source data or the generated category artifact.
   - Report unresolved `category_code` values as validation errors.
   - Keep `category_code` in the generated artifact as a stable relationship
     key; do not include Strapi relation IDs.
5. Define the subject artifact shape using the same envelope style established
   by Task 008:
   - `schema_version`
   - `workflow`
   - `source`
   - `strapi`
   - `records`
6. Add a formal subject artifact JSON Schema:
   - `tools/seed-data/config/subject_artifact.schema.json`
7. Validate generated subject artifacts against the subject artifact schema.
8. Generate:
   - `tools/seed-data/artifacts/subject/subjects.json`
9. Ensure artifact generation runs CSV validation and category-reference
   validation first, and does not write an artifact when source validation,
   reference validation, or artifact validation fails.
10. Add tests for subject source lookup, path display, CSV validation,
   reference validation, artifact generation, and artifact-schema validation.
11. Update `docs/interfaces/seed-data-artifacts.md` with the finalized subject
   artifact contract.
12. Update `tools/seed-data/README.md` with subject validation and generation
   commands.

## Out of Scope

- Creating or modifying Strapi 5 subject content-type schema files.
- Comparing `subject_artifact.schema.json` with the Strapi subject schema.
- Running Strapi compatibility checks.
- Ingesting subject records into Strapi.
- Dropping, recreating, or migrating any Strapi content type.

## Execution Results

### State Summary - 2026-07-10

#### What Was Built

- Created GitHub issue #45 for the combined Task 009 and Task 010
  implementation slice.
- Created branch `issue-45-category-subject-seed-artifacts`.
- Confirmed the downloaded Subject CSV shape differs from the earlier helper
  column expectation:
  - exported helper names are not present;
  - `category_code` is present directly;
  - optional tracking columns `from_date`, `to_date`, and `prabodhan_count` are
    present.
- Added Subject source helpers, path display support, CSV validation,
  category-reference validation, artifact generation, and artifact-schema
  validation.
- Added a formal Subject artifact schema:
  - `tools/seed-data/config/subject_artifact.schema.json`
- Generated the reviewable Subject artifact:
  - `tools/seed-data/artifacts/subject/subjects.json`
- Updated `docs/interfaces/seed-data-artifacts.md` with the durable Subject
  artifact contract.
- Updated `tools/seed-data/README.md` with Subject validation and generation
  commands.

#### What Works

- `gurubodh-seed-data subject validate --source subjects` validates the
  configured Subject CSV with 124 data rows and verifies every `category_code`
  against the Category source.
- `gurubodh-seed-data subject generate --source subjects` validates the CSV,
  validates category references, validates the generated artifact against the
  Subject artifact schema, and writes 124 records.
- Artifact generation aborts before writing when CSV validation or reference
  validation fails.
- Generated records include stable `subject_code` and `category_code` values and
  exclude Strapi internal identifiers and relation IDs.

#### Verification

- `tools/seed-data/.venv/bin/python -m unittest discover -s tools/seed-data/tests`
- `tools/seed-data/.venv/bin/gurubodh-seed-data subject validate --source subjects`
- `tools/seed-data/.venv/bin/gurubodh-seed-data subject generate --source subjects`
- `python3 -m json.tool tools/seed-data/config/subject_artifact.schema.json`
- `python3 -m json.tool tools/seed-data/artifacts/subject/subjects.json`

## Follow-Up

- Later Strapi schema compatibility and ingestion tasks should decide how to
  compare subject artifacts with the Strapi 5 subject Collection Type.
- Strapi 5 ingestion follows only after category, subject, and glossary artifact
  contracts are finalized and the relevant CMS content types are confirmed.
