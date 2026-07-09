# Task-012: Strapi Glossary Collection Types

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-07-09</date>
<owners>Gurubodh maintainers</owners>

## Goal

Create Strapi 5 Collection Types for Sanatan Glossary and Prabodhan Glossary
using the glossary contract finalized by Task 008.

## Context

Task 008 generates reviewable glossary seed-data JSON artifacts and records the
intended Strapi-facing contract in
`docs/interfaces/seed-data-artifacts.md`. Those artifacts are meant to be ready
for later Strapi ingestion, but Task 008 does not create the actual CMS
content-type schema files.

Sanatan Glossary and Prabodhan Glossary should be separate Strapi Collection
Types because they are maintained independently and may diverge over time.
Sanatan Glossary is sourced externally. Prabodhan Glossary is maintained by the
Gurubodh maintainers and may later require additional fields.

## Decisions

- Create separate Strapi Collection Types for Sanatan Glossary and Prabodhan
  Glossary.
- Keep term codes unique within each collection, not globally across both
  glossaries.
- Start both Collection Types with the shared fields documented in the
  seed-data artifact interface:
  - `term_code`
  - `term`
  - `definition`
- Do not add glossary relationships in the initial CMS schema.
- Let Strapi manage native `id`, Strapi 5 `documentId`, timestamps, and
  internal user fields.
- Keep ingestion logic out of this task; ingestion remains in Task 011.

## Approved Plan

1. Read `docs/interfaces/seed-data-artifacts.md` for the glossary artifact and
   Strapi Collection Type contract.
2. Add the Sanatan Glossary Strapi Collection Type schema under:
   - `apps/gurubodh-cms/src/api/sanatan-glossary/content-types/sanatan-glossary/schema.json`
3. Add the Prabodhan Glossary Strapi Collection Type schema under:
   - `apps/gurubodh-cms/src/api/prabodhan-glossary/content-types/prabodhan-glossary/schema.json`
4. Match existing CMS schema conventions used by the current category and
   subject content types.
5. Verify the CMS can build or otherwise validate the new content types using
   the CMS commands documented in `README.md` and `apps/gurubodh-cms/README.md`.
6. Update documentation if the implemented field names or CMS constraints differ
   from the contract recorded in the interface document.

## Execution Results

Pending.

## Follow-Up

- Task 011 should ingest generated seed-data artifacts only after the relevant
  Strapi Collection Types exist.
