# Task-012: Strapi Glossary Seed-Data Ingestion Plan

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-07-12</date>
<owners>Gurubodh maintainers</owners>
<github_issue>https://github.com/Team-Gurubodh/gurubodh/issues/63</github_issue>

## Goal

Define a defensive, multi-stage implementation plan for creating the Strapi 5
Glossary Collection Types and ingesting generated Sanatan Glossary and
Prabodhan Glossary seed-data JSON artifacts into those Collection Types.

The plan should avoid manual Admin UI entry for glossary seed data while
preserving the CMS as the system of record and keeping Strapi writes
observable, repeatable, and recoverable.

## Context

Task 008 produced reviewed glossary JSON artifacts:

```text
tools/seed-data/artifacts/glossary/sanatan-glossary.json
tools/seed-data/artifacts/glossary/prabodhan-glossary.json
```

Those artifacts are staging contracts, not direct Strapi REST payloads. The
ingestion implementation must translate artifact fields into Strapi fields,
confirm that the target Collection Types exist, and publish records.

The current reviewed artifact counts are:

- Sanatan Glossary: 5 records.
- Prabodhan Glossary: 19 records.

Unlike Category and Subject, Strapi is not presently aware of glossary
Collection Types. This task must therefore plan both:

1. Strapi Collection Type creation for the two glossary targets.
2. API-based glossary seed-data ingestion after those Collection Types exist.

Task 011 implemented the Category and Subject ingestion workflow. Glossary
ingestion should reuse the safe ingestion patterns from that task where they
fit, while keeping glossary-specific schema creation and adapter behavior
explicit.

Ingestion introduces runtime concerns that should remain separate from
CSV-to-JSON generation:

- Strapi Collection Type availability;
- API authentication;
- required CMS fields;
- Strapi Draft & Publish behavior;
- idempotent create/update behavior;
- dry-run reporting;
- conflict handling;
- recovery from partial local or staging writes.

## Decisions

- Model Sanatan Glossary and Prabodhan Glossary as separate Strapi 5 Collection
  Types.
- Use Strapi REST APIs for ingestion.
- Do not write directly to the Strapi database.
- Use stable business keys for reconciliation, not Strapi internal IDs.
- Let Strapi generate native `id` and Strapi 5 `documentId` values.
- Use `code` as the Strapi field name for the stable glossary term code.
- Map artifact `term_code` to Strapi `code`.
- Treat glossary codes as unique within each glossary collection, not globally
  across both glossary collections.
- Keep glossary `term` and `definition` fields non-localized for now.
- Enable Draft & Publish for both glossary Collection Types.
- Publish all ingested glossary records.
- Add dedicated glossary ingestion behavior after Collection Type readiness.
- Require dry-run behavior before live writes.
- Map artifact fields to Strapi fields explicitly; do not send artifact records
  directly to Strapi.
- Keep Category and Subject ingestion behavior unchanged.

## Target Field Mapping

### Sanatan Glossary

| Artifact field | Strapi field | Notes |
| --- | --- | --- |
| `term_code` | `code` | Stable key, non-localized, unique within Sanatan Glossary. |
| `term` | `term` | Non-localized, required. |
| `definition` | `definition` | Non-localized, required. |
| `source.key` | ignored | Used for provenance and artifact validation, not stored initially. |
| `strapi.collection_type` | target collection | Must resolve to the Sanatan Glossary Collection Type. |

### Prabodhan Glossary

| Artifact field | Strapi field | Notes |
| --- | --- | --- |
| `term_code` | `code` | Stable key, non-localized, unique within Prabodhan Glossary. |
| `term` | `term` | Non-localized, required. |
| `definition` | `definition` | Non-localized, required. |
| `source.key` | ignored | Used for provenance and artifact validation, not stored initially. |
| `strapi.collection_type` | target collection | Must resolve to the Prabodhan Glossary Collection Type. |

## Multi-Stage Implementation Plan

Each stage below is intended to be small enough to become one GitHub issue and
to be completed in a single focused implementation pass.

### Stage 1 - Strapi Glossary Schema Readiness

Goal: make the Strapi CMS capable of storing Sanatan Glossary and Prabodhan
Glossary records before ingestion tooling attempts any writes.

Scope:

1. Create Strapi API files for the Sanatan Glossary Collection Type:
   - `apps/gurubodh-cms/src/api/sanatan-glossary/content-types/sanatan-glossary/schema.json`;
   - route file;
   - controller file;
   - service file.
2. Create Strapi API files for the Prabodhan Glossary Collection Type:
   - `apps/gurubodh-cms/src/api/prabodhan-glossary/content-types/prabodhan-glossary/schema.json`;
   - route file;
   - controller file;
   - service file.
3. Add shared initial fields to both glossary Collection Types:
   - `code` as a required unique string field;
   - `term` as a required string or text field;
   - `definition` as a required text field.
4. Enable `draftAndPublish: true` for both glossary Collection Types.
5. Keep glossary fields non-localized.
6. Confirm the generated REST plural API IDs before hardcoding ingestion
   endpoint names.
7. Update schema documentation if schema ownership or field expectations
   change.

Defensive checks:

- Run JSON validation on the new Strapi schema files.
- Run the CMS build command documented in the CMS README.
- Start the CMS against a disposable local database when available and confirm
  Strapi boots with both glossary schemas.
- Confirm Sanatan Glossary and Prabodhan Glossary REST endpoints are reachable.
- Do not ingest data in this stage.

Expected output:

- Strapi can store and expose both glossary Collection Types through REST.
- No glossary seed-data writer exists yet.

### Stage 2 - Glossary Preflight And Artifact Loading

Goal: extend the existing ingestion foundation so it can inspect glossary
artifacts and Strapi glossary endpoints without performing writes by default.

Scope:

1. Load Sanatan Glossary and Prabodhan Glossary artifacts from their reviewed
   artifact locations.
2. Validate loaded glossary artifacts against
   `tools/seed-data/config/glossary_artifact.schema.json`.
3. Add read-only preflight checks for:
   - Strapi API reachability;
   - authenticated access to the Sanatan Glossary endpoint;
   - authenticated access to the Prabodhan Glossary endpoint;
   - Draft & Publish support for both glossary Collection Types.
4. Confirm that artifact `strapi.collection_type` values resolve only to
   approved glossary targets.
5. Add report output summarizing:
   - glossary artifact record counts;
   - configured Strapi target collections;
   - preflight pass/fail details.
6. Keep live writes unavailable in this stage.

Defensive checks:

- Unit-test glossary artifact loading and schema validation.
- Unit-test missing artifact behavior.
- Unit-test preflight failures when glossary endpoints are missing.
- Unit-test that Stage 2 commands cannot write.
- Mock Strapi responses for glossary endpoint access and Draft & Publish
  support.

Expected output:

- Maintainers can prove that glossary artifacts and Strapi glossary endpoints
  are ready before implementing writes.

### Stage 3 - Glossary Adapter, Dry-Run Planning, And Conflict Detection

Goal: plan Sanatan Glossary and Prabodhan Glossary ingestion safely before any
apply behavior is enabled.

Scope:

1. Implement a glossary ingestion adapter that can be parameterized by the
   target glossary artifact and target Strapi collection.
2. Map artifact fields explicitly:
   - `term_code` to `code`;
   - `term` to `term`;
   - `definition` to `definition`.
3. Query existing records in each glossary Collection Type by stable `code`.
4. Treat missing records as creates.
5. Treat matching records as updates when `term` or `definition` differ.
6. Treat records as matching when all mapped fields already match.
7. Report conflicts for:
   - duplicate artifact `term_code` values within the same glossary artifact;
   - duplicate existing Strapi records with the same `code` within the same
     glossary Collection Type;
   - missing required artifact values;
   - artifact `strapi.collection_type` not matching the expected target;
   - missing required Strapi fields;
   - unavailable or ambiguous Strapi glossary endpoint names.
8. Allow the same code value to exist once in Sanatan Glossary and once in
   Prabodhan Glossary without cross-glossary conflict.
9. Add shared report output summarizing:
   - records to create;
   - records to update;
   - records already matching;
   - conflicts;
   - blocked records;
   - skipped fields;
   - publish actions.
10. Plan publish actions for every created or updated glossary record.

Defensive checks:

- Unit-test glossary field mapping.
- Unit-test dry-run create/update/matching/conflict classification.
- Unit-test duplicate code detection within a glossary.
- Unit-test that duplicate codes across different glossary collections are not
  conflicts.
- Unit-test publish intent for all create/update records.
- Unit-test dry-run behavior cannot write.
- Integration-test read-only planning against a disposable Strapi instance when
  credentials and a clean local database are available.

Expected output:

- Glossary ingestion planning is reviewable and repeatable.
- No glossary records are written yet.

### Stage 4 - Glossary Apply, Publish, And Idempotency

Goal: ingest glossary records safely after dry-run planning is reliable.

Scope:

1. Require an explicit apply flag for writes.
2. Block apply when either glossary plan contains conflicts or blocked records.
3. Create or update Sanatan Glossary records by stable `code`.
4. Create or update Prabodhan Glossary records by stable `code`.
5. Publish every created or updated glossary record.
6. Re-query Strapi after apply and rebuild the glossary plan.
7. Report the final post-apply state.
8. Preserve Category and Subject ingestion behavior.

Defensive checks:

- Unit-test that apply mode requires an explicit flag.
- Unit-test that apply is blocked by conflicts in either glossary.
- Unit-test create/update/publish calls with mocked Strapi responses.
- Integration-test against a disposable Strapi instance after Stage 1 has
  created both glossary Collection Types.
- Verify final dry-run after apply reports no pending changes.

Expected output:

- Sanatan Glossary and Prabodhan Glossary can be ingested repeatedly without
  duplicates.
- Every ingested glossary record is published.

### Stage 5 - End-To-End Verification And Recovery Guidance

Goal: document and verify the complete operational path for maintainers.

Scope:

1. Add maintainer-facing documentation for:
   - required environment variables;
   - expected Strapi API token permissions;
   - clean local database recommendation;
   - glossary preflight commands;
   - glossary dry-run commands;
   - glossary apply commands;
   - expected report sections.
2. Add an end-to-end checklist:
   - validate Sanatan Glossary CSV;
   - validate Prabodhan Glossary CSV;
   - regenerate glossary artifacts only if reviewed CSV sources changed;
   - build CMS;
   - start CMS;
   - run glossary preflight;
   - run glossary dry-run;
   - apply glossary ingestion;
   - run glossary dry-run again;
   - inspect Strapi Admin for published glossary entries.
3. Document recovery actions:
   - missing glossary endpoint: complete schema readiness before ingestion;
   - dry-run conflict: fix source artifact or Strapi trial data before apply;
   - failed glossary apply: rerun glossary dry-run and reconcile by stable
     `code`;
   - wrong field mapping discovered before apply: fix adapter and rerun
     dry-run;
   - wrong field mapping discovered after apply: update by stable `code` after
     a dry-run report, not by direct database edits;
   - local trial data contamination: clean local tables or database only after
     backup and only outside production environments.
4. Record any Strapi-specific operational limitations discovered during
   integration testing.

Defensive checks:

- Run all unit tests for seed-data tooling.
- Run CMS build.
- Run documented glossary dry-run commands.
- Run apply commands only against an approved local or staging Strapi instance.
- Confirm repeated apply is idempotent by running dry-run after apply.

Expected output:

- Maintainers can operate the glossary ingestion workflow without clicking
  through Strapi Admin for every glossary term.
- The workflow is repeatable, reviewable, and recoverable.

## Execution Results

### Stage 2 - 2026-07-12

GitHub issue: https://github.com/Team-Gurubodh/gurubodh/issues/67

Implementation branch:

```text
issue-67-glossary-preflight-artifact-loading
```

Implemented read-only glossary ingestion preflight support in
`tools/seed-data`:

- added reviewed Sanatan Glossary and Prabodhan Glossary artifact loading for
  ingestion preflight;
- validates both artifacts against
  `tools/seed-data/config/glossary_artifact.schema.json`;
- verifies artifact `strapi.collection_type` values against the approved
  glossary targets only;
- checks authenticated read access and Draft & Publish status-query support for
  `sanatan-glossaries` and `prabodhan-glossaries`;
- added the command:

```bash
gurubodh-seed-data ingest glossary-preflight
```

Stage 2 intentionally performs no create, update, or publish writes.

Verification found that the command reached Strapi and initially received
`403 Forbidden` for both glossary endpoints while the same token passed
Category and Subject preflight. After updating the Strapi API token permissions,
the glossary preflight passed for both endpoint access and Draft & Publish
status queries.

## Out Of Scope

- Direct database writes.
- Frontend consumption behavior.
- RAG, metadata generation, or embedding updates.
- Automatic deletion of CMS records that are absent from artifacts.
- Localization of glossary fields.
- Cross-glossary relationship modeling.
- Combining Sanatan Glossary and Prabodhan Glossary into one shared Collection
  Type.
- Production execution without a separate production readiness decision.

## Acceptance Criteria

- The plan is split into issue-sized stages.
- Strapi glossary Collection Type readiness is planned before glossary
  ingestion.
- Sanatan Glossary and Prabodhan Glossary are separate Collection Types.
- Glossary fields are non-localized.
- The Strapi stable key field is named `code`.
- Artifact `term_code` maps explicitly to Strapi `code`.
- Dry-run is required before live writes.
- Live writes require an explicit apply flag.
- Field mapping is explicit and reviewed before implementation.
- All ingested glossary records are published.
- Duplicate codes are conflicts within one glossary collection but allowed
  across different glossary collections.
- Repeated apply is idempotent and does not create duplicates.
- No direct database writes are used.

## Execution Results

- 2026-07-12: Draft task record created for GitHub issue
  [#63](https://github.com/Team-Gurubodh/gurubodh/issues/63). Maintainers
  clarified the planning decisions:
  - keep Sanatan Glossary and Prabodhan Glossary as two separate Collection
    Types;
  - keep glossary fields non-localized;
  - publish all entries in both glossaries;
  - use `code` as the Strapi field name instead of `term_code`.
- 2026-07-12: Stage 1 implementation started under GitHub issue
  [#65](https://github.com/Team-Gurubodh/gurubodh/issues/65).
  - Added Sanatan Glossary and Prabodhan Glossary Strapi Collection Type API
    files with `code`, `term`, and `definition` fields.
  - Enabled Draft & Publish for both glossary Collection Types.
  - Confirmed generated REST plural API IDs:
    - `sanatan-glossaries`;
    - `prabodhan-glossaries`.
  - Ran Strapi schema JSON validation, `git diff --check`, Strapi type
    generation, and `make cms-build`.
  - Booted Strapi successfully against the throwaway local PostgreSQL database
    `gurubodh_db_copy`; unauthenticated route probes returned `403` for both
    glossary endpoints and `404` for a non-existent endpoint, confirming the
    glossary routes exist.
  - Initial authenticated probes with the available API token returned `403`
    for the glossary endpoints while existing Category and Subject probes
    returned `200`.
  - After the API token permissions were updated for the newly added glossary
    Collection Types, authenticated probes returned `200` for
    `sanatan-glossaries` and `prabodhan-glossaries`; both collections were
    reachable and empty as expected before ingestion.

## Follow-Up

- Create separate GitHub issues for individual stages if the implementation is
  split across multiple focused passes.
- Revisit the glossary artifact contract only if a future task decides that
  source artifact fields should also be renamed from `term_code` to `code`.
