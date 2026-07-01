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

## Planned Workflow

Future steps will add repeatable validation, CSV-to-JSON artifact generation,
and Strapi REST API ingestion. The seed-data tool will validate downloaded CSV
files before generating artifacts, even when spreadsheet validation and
conditional formatting are also configured for human data entry.

Generated artifacts must not include Strapi internal `id` or `documentId`
values. Strapi is responsible for generating those identifiers during API-based
ingestion.
