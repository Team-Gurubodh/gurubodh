# Task-008: Glossary Seed-Data JSON Artifacts

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-07-07</date>
<owners>Gurubodh maintainers</owners>

## Goal

Generate reviewable JSON artifacts for glossary seed-data sources using the
config-driven source discovery and artifact contract established in Task 007.

## Context

Glossary is the first implemented seed-data workflow. The current tool already
supports glossary source listing, path display, and CSV validation for:

- `sanatan-glossary`
- `prabodhan-glossary`

The next step is to move source definitions out of Python constants and produce
validated JSON artifacts suitable for later Strapi 5 ingestion.

## Decisions

- Preserve existing glossary validation behavior unless this task explicitly
  changes it.
- Run validation before writing any generated artifact.
- Abort artifact generation when validation reports errors.
- Include glossary source identity in the generated artifact.
- Do not include Strapi internal `id` or `documentId` values.
- Keep Strapi compatibility checks out of this task.

## Approved Plan

1. Load glossary source definitions from `seed_data_sources.json`.
2. Preserve existing commands where practical:
   - `gurubodh-seed-data glossary sources`
   - `gurubodh-seed-data glossary paths`
   - `gurubodh-seed-data glossary validate --source <source-key>`
3. Add a glossary generation command, likely:
   - `gurubodh-seed-data glossary generate --source sanatan-glossary`
   - `gurubodh-seed-data glossary generate --source prabodhan-glossary`
4. Generate artifacts under:
   - `tools/seed-data/artifacts/glossary/sanatan-glossary.json`
   - `tools/seed-data/artifacts/glossary/prabodhan-glossary.json`
5. Define and test the first glossary artifact shape.
6. Update `tools/seed-data/README.md` with generation commands and artifact
   behavior.

## Execution Results

Pending.

## Follow-Up

- Category artifact generation follows in Task 009.
- Strapi ingestion follows later in Task 011.
