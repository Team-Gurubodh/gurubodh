# Seed Data

Seed-data tooling prepares and ingests durable reference data for the Gurubodh
CMS. This tool starts with glossary terms and is intended to grow incrementally
to support other CMS seed-data workflows such as categories and subjects.

## Purpose

The first workflow supports externally maintained glossaries of philosophical
terms. These glossaries are maintained outside Strapi so domain experts and
volunteers can contribute without needing to learn the Strapi admin interface.
After successful ingestion, the CMS remains the system of record.

The initial glossary sources are:

- `sanatan-glossary` - Sanatan Glossary
- `prabodhan-glossary` - Prabodhan Glossary

Both sources are expected to use the same spreadsheet columns:

- `Sr No`
- `Term Code`
- `Term`
- `Definition`

The Google Sheet links will be recorded here once available.

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

## File Locations

Manually downloaded Google Sheet CSV files belong under:

```text
sources/glossary/
```

Generated, reviewable JSON artifacts belong under:

```text
artifacts/glossary/
```

Expected glossary file names:

```text
sources/glossary/sanatan-glossary.csv
sources/glossary/prabodhan-glossary.csv
artifacts/glossary/sanatan-glossary.json
artifacts/glossary/prabodhan-glossary.json
```

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

## Planned Workflow

Future steps will add CSV-to-JSON artifact generation and Strapi REST API
ingestion. The seed-data tool validates downloaded CSV files before generating
artifacts, even when spreadsheet validation and conditional formatting are also
configured for human data entry.

Generated artifacts must not include Strapi internal `id` or `documentId`
values. Strapi is responsible for generating those identifiers during API-based
ingestion.
