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

Generated glossary artifacts are reviewable project data and are expected to be
committed after they are regenerated and verified.

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

The Subject sheet also includes `category_name_en` and `category_name_hi-IN`
helper columns. Choose a Category by either English or Hindi name, and the
`category_code` column is auto-filled from the `Categories` sheet. If both
helper names are filled but resolve to different Category codes, the setup
script highlights the mismatch.

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

## Planned Workflow

Future steps will add CSV-to-JSON artifact generation for category and subject
seed data, Strapi Collection Types for glossary data, and Strapi REST API
ingestion. The seed-data tool validates downloaded CSV files before generating
artifacts, even when spreadsheet validation and conditional formatting are also
configured for human data entry.

Strapi ingestion remains a separate workflow. It should read generated artifacts
after the relevant Strapi Collection Types already exist.
