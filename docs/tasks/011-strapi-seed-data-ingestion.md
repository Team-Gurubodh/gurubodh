# Task-011: Strapi Seed-Data Ingestion

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-07-07</date>
<owners>Gurubodh maintainers</owners>

## Goal

Ingest generated category, subject, and glossary seed-data JSON artifacts into
Strapi 5 through an idempotent API-based workflow.

## Context

Tasks 008, 009, and 010 produce reviewed JSON artifacts. This task connects
those artifacts to Strapi 5 content types after the artifact shapes and stable
keys are defined.

For glossary seed data, the Sanatan Glossary and Prabodhan Glossary Collection
Types should already exist before this task begins. Task 012 is responsible for
creating those Collection Types from the contract recorded by Task 008.

Ingestion introduces runtime concerns that should remain separate from
CSV-to-JSON generation:

- API authentication;
- Strapi content-type availability;
- required CMS fields;
- relationship resolution;
- idempotent create/update behavior;
- dry-run reporting;
- conflict handling.

## Decisions

- Use Strapi REST APIs for ingestion.
- Do not write directly to the Strapi database.
- Use stable business keys for reconciliation, not Strapi internal IDs.
- Let Strapi generate native `id` and Strapi 5 `documentId` values.
- Add dry-run behavior before live writes.
- Use Strapi MCP or schema inspection here if useful, not during artifact
  generation.
- Do not create or mutate Strapi Collection Type schemas as part of ingestion.

## Approved Plan

1. Confirm target Strapi content types and field names for category, subject,
   and glossary records. For glossary records, use the Collection Types created
   by Task 012.
2. Define per-type ingestion mappings from JSON artifact fields to Strapi API
   payloads.
3. Add dry-run mode that reports:
   - records to create;
   - records to update;
   - missing required fields;
   - unresolved relationships;
   - artifact fields not present in Strapi;
   - optional Strapi fields missing from artifacts.
4. Add idempotent create/update behavior:
   - create when stable key is absent in Strapi;
   - update allowed fields when stable key already exists;
   - fail on unresolved relationship keys;
   - never send Strapi internal identifiers from artifacts.
5. Define conflict handling:
   - missing required Strapi field: error;
   - unresolved relationship: error;
   - missing target content type: error;
   - artifact field missing in Strapi: warning or blocked change depending on
     whether the field is intentionally new;
   - optional Strapi field missing from artifact: warning;
   - changed updateable existing field: planned update in dry-run.
6. Add tests around payload construction and conflict classification.
7. Verify against a Strapi instance only when API credentials and a running CMS
   are available.

## Execution Results

Pending.

## Follow-Up

- Later tasks may add richer synchronization reports, rollback guidance, or
  environment-specific ingestion workflows.
