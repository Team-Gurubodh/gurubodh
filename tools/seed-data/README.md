# Seed Data

Seed-data tooling prepares and ingests durable reference data for the Gurubodh
CMS. The tool is evolving into the canonical workflow for externally maintained
`glossary`, `category`, and `subject` seed data.

## Purpose

Seed data is maintained outside Strapi so domain experts and volunteers can
contribute through familiar spreadsheet workflows. CSV exports are validated and
converted into reviewable JSON artifacts before later Strapi 5 ingestion. After
successful ingestion, the CMS remains the system of record.

The current seed-data source types are:

- `category`
- `subject`
- `glossary`

The initial glossary sources are:

- `sanatan-glossary` - Sanatan Glossary
- `prabodhan-glossary` - Prabodhan Glossary

Both sources are expected to use the same spreadsheet columns:

- `Sr No`
- `Term Code`
- `Term`
- `Definition`

The Google Sheet links will be recorded here once available.

The Category source is:

- `categories` - Categories

The current Category CSV columns are:

- `code`
- `legacy_code`
- `is_active`
- `sort_order`
- `desired_status`
- `name_en`
- `description_en`
- `name_hi-IN`
- `description_hi-IN`

The Subject source is:

- `subjects` - Subjects

The current Subject CSV columns are:

- `code`
- `legacy_code`
- `is_active`
- `sort_order`
- `category_code`
- `desired_status`
- `name_en`
- `description_en`
- `name_hi-IN`
- `description_hi-IN`
- `from_date`
- `to_date`
- `prabodhan_count`

The lightweight interface contract for source CSV files, generated artifacts,
and future Strapi ingestion is documented in
`docs/interfaces/seed-data-artifacts.md`.

## Setup

Run these commands from the monorepo root:

```bash
cd tools/seed-data
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
gurubodh-seed-data --help
```

## Current Commands

List supported seed-data workflows:

```bash
gurubodh-seed-data workflows
```

List supported glossary sources:

```bash
gurubodh-seed-data glossary sources
```

List canonical glossary input and output paths:

```bash
gurubodh-seed-data glossary paths
```

Show paths for one glossary source:

```bash
gurubodh-seed-data glossary paths --source sanatan-glossary
```

Validate one downloaded glossary CSV source:

```bash
gurubodh-seed-data glossary validate --source sanatan-glossary
gurubodh-seed-data glossary validate --source prabodhan-glossary
```

Generate one glossary JSON artifact:

```bash
gurubodh-seed-data glossary generate --source sanatan-glossary
gurubodh-seed-data glossary generate --source prabodhan-glossary
```

List supported category or subject sources:

```bash
gurubodh-seed-data category sources
gurubodh-seed-data subject sources
```

List canonical category or subject input and output paths:

```bash
gurubodh-seed-data category paths
gurubodh-seed-data subject paths
```

Validate category and subject CSV sources:

```bash
gurubodh-seed-data category validate --source categories
gurubodh-seed-data subject validate --source subjects
```

Generate category and subject JSON artifacts:

```bash
gurubodh-seed-data category generate --source categories
gurubodh-seed-data subject generate --source subjects
```

Run read-only Strapi ingestion preflight checks:

```bash
export GURUBODH_STRAPI_URL=http://localhost:1337
export GURUBODH_STRAPI_API_TOKEN=<token>
gurubodh-seed-data ingest preflight
```

Load reviewed Sanatan Glossary and Prabodhan Glossary artifacts, validate their
approved Strapi targets, and run read-only glossary endpoint preflight checks:

```bash
gurubodh-seed-data ingest glossary-preflight
```

Load reviewed Sanatan Glossary and Prabodhan Glossary artifacts, run glossary
preflight checks, and print the read-only glossary ingestion dry-run plan:

```bash
gurubodh-seed-data ingest glossary-plan
```

`ingest glossary-plan` is dry-run by default. It plans Sanatan Glossary and
Prabodhan Glossary creates, updates, matching records, conflicts, blocked
records, and publish actions. To write glossary records to an approved
disposable or staging Strapi instance, pass the explicit apply flag:

```bash
gurubodh-seed-data ingest glossary-plan --apply
```

After a successful glossary apply, rerun the default dry-run command. A clean
apply should report no pending glossary creates, updates, conflicts, blocked
records, or publish actions.

Load reviewed Category and Subject artifacts, run preflight, and print the
Category and Subject ingestion dry-run report:

```bash
gurubodh-seed-data ingest plan
```

`ingest plan` is dry-run by default. It plans Category and Subject creates,
updates, matches, conflicts, blocked records, relation resolution, and publish
actions. To write Category and Subject records to an approved disposable or
staging Strapi instance, pass the explicit apply flag:

```bash
gurubodh-seed-data ingest plan --apply
```

After a successful apply, rerun the default dry-run command. A clean apply
should report no pending Category or Subject creates, updates, conflicts,
blocked records, or publish actions.

## File Locations

Manually downloaded Google Sheet CSV files are moving to the external source
root:

```text
/Users/rajeev/Gurubodh_library/seed_data/csv_import
```

Expected CSV source paths under that root are:

```text
category/categories.csv
glossary/sanatan-glossary.csv
glossary/prabodhan-glossary.csv
subject/subjects.csv
```

Generated, reviewable JSON artifacts belong under this tool's artifact
directory:

```text
artifacts/category/categories.json
artifacts/glossary/sanatan-glossary.json
artifacts/glossary/prabodhan-glossary.json
artifacts/subject/subjects.json
```

Source definitions live in:

```text
config/seed_data_sources.json
```

The configuration is described by:

```text
config/seed_data_sources.schema.json
```

Glossary artifacts are described by:

```text
config/glossary_artifact.schema.json
```

Category, glossary, and subject artifacts are described by:

```text
config/category_artifact.schema.json
config/glossary_artifact.schema.json
config/subject_artifact.schema.json
```

Generated seed-data artifacts are reviewable project data and are expected to
be committed after they are regenerated and verified.

## Category and Subject Spreadsheet Validation

Google Sheets setup scripts for Category and Subject seed-data authoring live
under:

```text
scripts/google-sheets/
```

Current scripts:

```text
scripts/google-sheets/append-columns.gs
scripts/google-sheets/category-validations.gs
scripts/google-sheets/export-csv.gs
scripts/google-sheets/shared-on-edit.gs
scripts/google-sheets/subject-validations.gs
```

Use these scripts from Google Sheets by opening **Extensions > Apps Script** and
adding the Category, Subject, and shared edit-trigger script files to the same
Apps Script project. Then run:

```text
setupCategorySeedDataSheet()
setupSubjectSeedDataSheet()
```

Run the Category setup before the Subject setup when both sheets are in the same
spreadsheet. The Subject script validates `category_code` against the Category
codes in the `Categories` sheet.

To append optional Subject tracking columns to an existing `Subjects` sheet,
add `append-columns.gs` to the same Apps Script project and run:

```text
appendSubjectSeedDataColumns()
```

The append script adds any missing `from_date`, `to_date`, and
`prabodhan_count` columns after the current last column. It is safe to re-run:
existing columns are skipped, and validations, formatting, and default values
are applied only to columns newly created by that run.

To export Category and Subject seed-data CSV files, add `export-csv.gs` to the
same Apps Script project and run:

```text
exportCategorySubjectSeedDataCsv()
```

The export script creates or updates `categories.csv` and `subjects.csv` in the
same Google Drive folder as the spreadsheet. Download those files and save them
locally under the external CSV source root:

```text
/Users/rajeev/Gurubodh_library/seed_data/csv_import/category/categories.csv
/Users/rajeev/Gurubodh_library/seed_data/csv_import/subject/subjects.csv
```

The Category and Subject scripts use one row per seed-data record. Non-localized
fields such as `code`, `legacy_code`, `is_active`, and `sort_order` appear once.
Localized fields are represented as locale-specific columns such as `name_en`,
`description_en`, `name_hi-IN`, and `description_hi-IN`.

The Subject Google Sheet setup script includes `category_name_en` and
`category_name_hi-IN` helper columns. Choose a Category by either English or
Hindi name, and the `category_code` column is auto-filled from the `Categories`
sheet. If both helper names are filled but resolve to different Category codes,
the setup script highlights the mismatch. The current downloaded Subject CSV
uses the exported `category_code` relationship key directly and includes
optional tracking columns: `from_date`, `to_date`, and `prabodhan_count`.

These spreadsheet validations are entry-time guidance for maintainers. The
seed-data tooling should still validate exported source files before generating
artifacts or ingesting data.

## Validation

Glossary validation checks the manually downloaded CSV before any generated
JSON artifact is created. The validator currently checks:

- required headers: `Sr No`, `Term Code`, `Term`, and `Definition`
- required field values
- `Term Code` format and range: `T00001` through `T50000`
- duplicate `Term` values within the same glossary source after removing all
  whitespace
- malformed rows with the wrong number of columns
- blank rows
- leading or trailing whitespace in `Term` values

Duplicate-term validation builds the comparison key by removing all Unicode
whitespace from the `Term` value. For example, `सूक्ष्म देह`, `सूक्ष्मदेह`, and
` सूक्ष्म  देह ` are treated as the same term for uniqueness checks.

Whitespace findings are reported separately from duplicate-term findings.
Leading or trailing whitespace in `Term` values is reported as an error with
the cell value included in the message. Internal whitespace in multi-word terms
is allowed and does not produce an error. Whitespace in other columns is not
checked. Required field, term-code, duplicate-term, malformed-row, and
blank-row issues are reported as errors.

CSV-to-JSON artifact generation must run validation first and must abort before
writing an artifact when validation reports any errors.

Category validation checks:

- required headers in expected order
- required values for `code`, `is_active`, `sort_order`, `desired_status`, and
  `name_en`
- `code` format: `CATnnn`
- duplicate non-empty `code`, `legacy_code`, and `sort_order` values
- boolean parsing for `is_active`
- integer parsing for `sort_order`
- `desired_status` values: `draft` or `published`
- maximum length rules for `legacy_code`, `name_en`, and `name_hi-IN`
- malformed rows and blank rows

Subject validation checks:

- required headers in expected order
- required values for `code`, `is_active`, `sort_order`, `category_code`,
  `desired_status`, and `name_en`
- `code` format: `SUBnnn`
- `category_code` format: `CATnnn`
- duplicate non-empty `code`, `legacy_code`, and `sort_order` values
- boolean parsing for `is_active`
- integer parsing for `sort_order`
- optional `from_date` and `to_date` format: `YYYY-MM-DD`
- optional integer parsing for `prabodhan_count`
- `desired_status` values: `draft` or `published`
- maximum length rules for `legacy_code`, `name_en`, and `name_hi-IN`
- unresolved `category_code` references against the Category source
- malformed rows and blank rows

## Glossary Artifact Generation

Glossary generation reads the configured CSV source, runs the same validation as
the `validate` command, parses the valid rows, and writes deterministic JSON
under `artifacts/glossary/`.

The current generated glossary artifacts are:

```text
artifacts/glossary/sanatan-glossary.json
artifacts/glossary/prabodhan-glossary.json
```

Each artifact includes:

- `schema_version`
- `workflow`
- `source`
- `strapi`
- `records`

The `strapi` object records the intended future Strapi Collection Type target.
The artifact is not itself a Strapi content-type schema. The actual Strapi
Collection Type schema files will be created by a later CMS task.

Generated artifacts must not include Strapi internal `id` or `documentId`
values. Strapi is responsible for generating those identifiers during API-based
ingestion.

## Category And Subject Artifact Generation

Category generation reads `category/categories.csv`, runs Category validation,
validates the generated artifact against
`config/category_artifact.schema.json`, and writes:

```text
artifacts/category/categories.json
```

Subject generation reads `subject/subjects.csv`, runs Subject validation,
validates `category_code` references against the Category source, validates the
generated artifact against `config/subject_artifact.schema.json`, and writes:

```text
artifacts/subject/subjects.json
```

Both workflows include source identity and intended future Strapi target
metadata. Subject artifacts keep `category_code` as a stable relationship key
and do not include Strapi relation IDs.

## Strapi Ingestion Workflow

The seed-data tool validates downloaded CSV files before generating artifacts,
even when spreadsheet validation and conditional formatting are also configured
for human data entry.

Strapi ingestion remains a separate workflow. It should read generated artifacts
after the relevant Strapi Collection Types already exist.

Category and Subject ingestion use the Strapi REST API and never write directly
to the PostgreSQL database. Both adapters reconcile records by stable `code`,
write English fields to the default locale, write Hindi fields to `hi-IN`,
publish all created or updated records, and ignore artifact `desired_status`.
Subject ingestion resolves the `category` relation from the artifact
`category_code` to the target Category `documentId`.

The current ingestion command plans and applies Category and Subject records
together. In apply mode, it writes Categories first, replans both workflows, and
then writes Subjects only if the Category plan is conflict-free and all Subject
Category relations resolve. This preserves the Category-before-Subject
dependency without exposing separate Category-only and Subject-only maintainer
commands.

### Strapi Requirements

Run ingestion only against an approved local or staging Strapi instance. For
local integration testing, prefer a clean throwaway PostgreSQL database so trial
data, duplicate codes, or duplicate sort orders do not hide ingestion issues.

The CMS must already provide these Collection Types and REST endpoints:

- `category`
- `subject`

The expected locale setup is:

- Strapi default locale: `en`
- Hindi localization locale: `hi-IN`

The default locale must be English because the ingestion adapters write
`name_en` and `description_en` into the default locale entry. The `hi-IN`
locale must exist before ingestion so Hindi localizations can be created or
updated.

Set these environment variables before running ingestion commands:

```bash
export GURUBODH_STRAPI_URL=http://localhost:1337
export GURUBODH_STRAPI_API_TOKEN=<token>
```

The API token must be kept out of tracked files. It needs enough permissions to:

- read `categories` and `subjects`;
- create and update `categories` and `subjects`;
- read `/api/i18n/locales`;
- query draft and published Category and Subject records;
- publish Category and Subject records through Strapi REST writes using
  `status=published`.

If a non-default local setup uses different locale codes, pass them explicitly:

```bash
gurubodh-seed-data ingest preflight \
  --default-locale en \
  --localized-locale hi-IN
```

Keep production ingestion out of this workflow until a separate production
readiness decision has been accepted.

### Preflight And Reports

Run a read-only preflight before planning or applying writes:

```bash
gurubodh-seed-data ingest preflight
```

The preflight report includes these checks:

- Category endpoint access;
- Subject endpoint access;
- default locale suitability for English fields;
- `hi-IN` locale availability;
- Draft & Publish status-query support for Categories;
- Draft & Publish status-query support for Subjects.

Run the dry-run planner:

```bash
gurubodh-seed-data ingest plan
```

The ingestion report includes:

- artifact record counts for Category and Subject;
- records to create;
- records to update;
- records already matching;
- conflicts;
- blocked records;
- skipped fields;
- publish actions;
- explanatory messages.

`desired_status` should appear under skipped fields. This is expected because
the current ingestion workflow publishes all ingested Category and Subject
records regardless of artifact `desired_status`.

### End-To-End Checklist

Use this checklist for local or staging verification:

1. Activate the seed-data virtual environment:

   ```bash
   cd tools/seed-data
   . .venv/bin/activate
   ```

2. Validate the Category source CSV:

   ```bash
   gurubodh-seed-data category validate --source categories
   ```

3. Validate the Subject source CSV:

   ```bash
   gurubodh-seed-data subject validate --source subjects
   ```

4. Regenerate artifacts only if the reviewed CSV sources changed:

   ```bash
   gurubodh-seed-data category generate --source categories
   gurubodh-seed-data subject generate --source subjects
   ```

5. Build the CMS from the monorepo root:

   ```bash
   make cms-build
   ```

6. Start Strapi against the approved throwaway or staging database:

   ```bash
   make cms-dev
   ```

7. Export the Strapi URL and API token in the ingestion shell:

   ```bash
   export GURUBODH_STRAPI_URL=http://localhost:1337
   export GURUBODH_STRAPI_API_TOKEN=<token>
   ```

8. Run read-only preflight:

   ```bash
   gurubodh-seed-data ingest preflight
   ```

9. Run the Category and Subject dry-run plan:

   ```bash
   gurubodh-seed-data ingest plan
   ```

10. Review the dry-run report. Continue only when conflicts and blocked records
    are both zero.

11. Apply Category and Subject ingestion:

    ```bash
    gurubodh-seed-data ingest plan --apply
    ```

12. Run the dry-run plan again:

    ```bash
    gurubodh-seed-data ingest plan
    ```

13. Confirm the final dry-run reports:

    - `Records to create: 0`
    - `Records to update: 0`
    - `Conflicts: 0`
    - `Blocked records: 0`
    - `Publish actions: 0`

14. Inspect Strapi Admin and spot-check that Category and Subject records are
    published in English and have `hi-IN` localizations. For Subjects, confirm
    Category relations and optional `from_date`, `to_date`, and
    `prabodhan_count` values where present.

### Recovery Guidance

Dry-run conflicts should be fixed before apply. Correct the source CSV and
regenerate artifacts when the artifact is wrong, or clean the local/staging
Strapi trial data when the CMS contains duplicate codes or sort-order
collisions.

If Category apply fails, stop before trusting Subject ingestion. Rerun
`gurubodh-seed-data ingest plan` and resolve Category conflicts or partial
updates before trying apply again.

If Subject apply fails, rerun the dry-run after confirming Category records
exist and have stable `documentId` values. Subject records with missing or
ambiguous Category targets remain blocked until the Category data is corrected.

If a field mapping problem is found before apply, fix the adapter and rerun the
dry-run. If a field mapping problem is found after apply, update records through
the ingestion workflow by stable `code` after reviewing a fresh dry-run report.
Do not repair mapped data with direct database edits.

If local trial data is contaminated, clean local tables or recreate the
throwaway database only after taking any needed backup. Do not use this cleanup
guidance for production data.

### Operational Limitations

Current Category and Subject ingestion is intentionally additive and
update-oriented. It does not delete Strapi records that are absent from the
artifacts.

The CLI exposes one combined Category and Subject ingestion plan. Maintainers
cannot currently run a Category-only or Subject-only apply command without code
changes, although the apply sequence is internally Category-first.

The report is aggregated across Category and Subject records. It does not yet
print per-record diffs for every planned change, so maintainers should inspect
the source artifacts and Strapi Admin when a dry-run reports unexpected updates.

The workflow has been verified for Strapi 5 REST localization writes using
`PUT /api/<collection>/{documentId}?locale=hi-IN&status=published`. Recheck this
behavior after Strapi upgrades or content-type localization changes.
