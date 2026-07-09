# Task-008: Glossary Seed-Data JSON Artifacts

<record_type>task_history</record_type>
<status>completed</status>
<date>2026-07-09</date>
<owners>Gurubodh maintainers</owners>
<github_issue>https://github.com/Team-Gurubodh/gurubodh/issues/41</github_issue>

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

Task 008 is a durable bridge between externally maintained glossary CSV files
and later Strapi ingestion. It should finalize the seed-data artifact shape and
record the intended Strapi Collection Type contract, but it should not create
the actual Strapi CMS content-type schema files.

## Decisions

- Preserve existing glossary validation behavior unless this task explicitly
  changes it.
- Run validation before writing any generated artifact.
- Abort artifact generation when validation reports errors.
- Include glossary source identity in the generated artifact.
- Do not include Strapi internal `id` or `documentId` values.
- Keep Strapi compatibility checks out of this task.
- Treat Sanatan Glossary and Prabodhan Glossary as separate future Strapi
  Collection Types.
- Treat glossary term codes as unique within each glossary collection, not
  globally across both glossary sources.
- Keep glossary artifacts independent of glossary relationships for now.
- Define a formal glossary artifact JSON Schema under
  `tools/seed-data/config/glossary_artifact.schema.json`.
- Record the durable artifact and intended Strapi Collection Type contract in
  `docs/interfaces/seed-data-artifacts.md`.
- Keep actual Strapi Collection Type schema creation in a separate follow-up
  task so Task 011 can stay focused on ingestion logic.
- Make generated glossary artifacts reviewable project data instead of ignored
  local-only outputs.

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
6. Add a glossary artifact JSON Schema under:
   - `tools/seed-data/config/glossary_artifact.schema.json`
7. Validate generated glossary artifacts against the glossary artifact schema.
8. Update `.gitignore` so generated seed-data artifacts can be reviewed and
   committed directly, while local seed-data sources remain ignored.
9. Update `docs/interfaces/seed-data-artifacts.md` with the finalized glossary
   artifact contract and intended Strapi Collection Type contract.
10. Update `tools/seed-data/README.md` with generation commands and artifact
   behavior.

## Planning Notes

### 2026-07-09 Assessment Follow-Up

Before implementation, maintainers clarified the boundary between seed-data
artifacts, artifact JSON Schemas, and Strapi Collection Type schemas.

A generated glossary artifact is a JSON data file containing records parsed from
CSV and prepared for later ingestion. A glossary artifact JSON Schema validates
that generated artifact. A Strapi Collection Type schema is a separate CMS model
definition stored under the Strapi application. The seed-data artifact schema
and the Strapi Collection Type schema are related by contract, but they are not
the same file and do not have the same responsibility.

Task 008 should therefore produce and validate reviewable seed-data artifacts,
but should not add files such as:

```text
apps/gurubodh-cms/src/api/sanatan-glossary/content-types/sanatan-glossary/schema.json
apps/gurubodh-cms/src/api/prabodhan-glossary/content-types/prabodhan-glossary/schema.json
```

Those CMS files belong to a separate follow-up task that can read the durable
contract in `docs/interfaces/seed-data-artifacts.md`.

Sanatan Glossary and Prabodhan Glossary will become two separate Strapi
Collection Types. Both source CSV files may therefore use `T00001`, `T00002`,
and so on without conflict. Term codes are stable business keys within each
target collection, not globally across all glossary sources.

The initial glossary artifact should be one artifact per future Strapi
Collection Type. Each artifact should include the source glossary identity and
the intended Strapi target. The source identity is still useful even though the
collections are separate, because it preserves provenance and makes generated
files self-describing.

The durable contract belongs in `docs/interfaces/seed-data-artifacts.md`, not
only in this task-history file. This task record preserves the planning context,
while the interface document gives future tasks a stable place to find the
contract.

Generated artifacts should be treated as reviewable project data for this
workflow. The current `.gitignore` ignores `tools/seed-data/artifacts/`; Task
008 should revise that rule directly instead of relying on exception-heavy
ignore patterns.

## Execution Results

### State Summary - 2026-07-09

#### What Was Built

- Created GitHub issue #41 for this implementation slice.
- Created branch `issue-41-glossary-json-artifacts`.
- Added a formal glossary artifact schema:
  - `tools/seed-data/config/glossary_artifact.schema.json`
- Added glossary artifact generation helpers.
- Added the CLI command:
  - `gurubodh-seed-data glossary generate --source <source-key>`
- Generated reviewable glossary artifacts:
  - `tools/seed-data/artifacts/glossary/sanatan-glossary.json`
  - `tools/seed-data/artifacts/glossary/prabodhan-glossary.json`
- Updated `.gitignore` so generated seed-data artifacts can be tracked while
  local seed-data source files remain ignored.
- Updated `docs/interfaces/seed-data-artifacts.md` with the durable glossary
  artifact contract and intended Strapi Collection Type contract.
- Added Task 012 to create the actual Strapi glossary Collection Types later.
- Updated Task 011 so ingestion assumes the required glossary Collection Types
  already exist.
- Updated seed-data documentation and schema documentation.

#### What Works

- `gurubodh-seed-data glossary generate --source sanatan-glossary` validates the
  configured Sanatan Glossary CSV and writes a JSON artifact with 5 records.
- `gurubodh-seed-data glossary generate --source prabodhan-glossary` validates
  the configured Prabodhan Glossary CSV and writes a JSON artifact with 19
  records.
- Artifact generation aborts before writing when CSV validation fails.
- Generated artifacts include source identity and intended Strapi target
  metadata.
- Generated artifact records exclude Strapi internal identifiers such as `id`
  and `documentId`.
- The generated JSON artifacts are valid JSON and match the task's glossary
  artifact contract.

#### Verification

- `python3 -m compileall tools/seed-data/gurubodh_seed_data tools/seed-data/tests`
- `tools/seed-data/.venv/bin/python -m unittest discover -s tools/seed-data/tests`
- `tools/seed-data/.venv/bin/gurubodh-seed-data glossary validate --source sanatan-glossary`
- `tools/seed-data/.venv/bin/gurubodh-seed-data glossary validate --source prabodhan-glossary`
- `tools/seed-data/.venv/bin/gurubodh-seed-data glossary generate --source sanatan-glossary`
- `tools/seed-data/.venv/bin/gurubodh-seed-data glossary generate --source prabodhan-glossary`
- `python3 -m json.tool tools/seed-data/config/glossary_artifact.schema.json`
- `python3 -m json.tool tools/seed-data/artifacts/glossary/sanatan-glossary.json`
- `python3 -m json.tool tools/seed-data/artifacts/glossary/prabodhan-glossary.json`

## Follow-Up

- Category artifact generation follows in Task 009.
- Strapi glossary Collection Type creation follows in Task 012.
- Strapi ingestion follows later in Task 011, after the required Collection
  Types exist.
