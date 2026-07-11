# Task-011: Strapi Category and Subject Seed-Data Ingestion Plan

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-07-10</date>
<owners>Gurubodh maintainers</owners>
<github_issue>https://github.com/Team-Gurubodh/gurubodh/issues/47</github_issue>

## Goal

Define a defensive, multi-stage implementation plan for ingesting generated
Category and Subject seed-data JSON artifacts into their corresponding Strapi 5
Collection Types.

The plan should avoid manual Admin UI entry for Category and Subject seed data
while preserving the CMS as the system of record and keeping Strapi writes
observable, repeatable, and recoverable.

## Context

Tasks 009 and 010 produce reviewed Category and Subject JSON artifacts:

```text
tools/seed-data/artifacts/category/categories.json
tools/seed-data/artifacts/subject/subjects.json
```

Those artifacts are staging contracts, not direct Strapi REST payloads. The
ingestion implementation must translate artifact fields into Strapi fields,
resolve relationships, apply localization behavior, and publish records.

The current reviewed artifact counts are:

- Category: 11 records.
- Subject: 124 records.

Glossary seed data is intentionally out of scope for this task. Glossary
Collection Type creation and glossary ingestion should be planned separately
after Category and Subject ingestion is working confidently.

Ingestion introduces runtime concerns that should remain separate from
CSV-to-JSON generation:

- API authentication;
- Strapi content-type availability;
- required CMS fields;
- relationship resolution;
- i18n locale handling;
- Strapi Draft & Publish behavior;
- idempotent create/update behavior;
- dry-run reporting;
- conflict handling.

## Decisions

- Use Strapi REST APIs for ingestion.
- Do not write directly to the Strapi database.
- Use stable business keys for reconciliation, not Strapi internal IDs.
- Let Strapi generate native `id` and Strapi 5 `documentId` values.
- Keep Category and Subject ingestion in scope.
- Keep Glossary ingestion out of scope.
- Add dedicated Category and Subject ingestion adapters.
- Require dry-run behavior before live writes.
- Map artifact fields to Strapi fields explicitly; do not send artifact records
  directly to Strapi.
- Resolve Subject-to-Category relationships by Category stable code.
- Add Subject schema support for:
  - `from_date` as an optional Strapi `date` field;
  - `to_date` as an optional Strapi `date` field;
  - `prabodhan_count` as an optional Strapi `integer` field.
- Keep Category and Subject `name` and `description` fields localized.
- Ingest English artifact fields as the default locale entry, after confirming
  the Strapi default locale is configured for English content.
- Ingest Hindi artifact fields as the `hi-IN` localization for the same Strapi
  document.
- Publish all ingested Category and Subject records regardless of artifact
  `desired_status`.
- Keep `desired_status` in the artifacts for now, but ignore it during this
  ingestion workflow.

## Target Field Mapping

### Category

| Artifact field | Strapi field | Notes |
| --- | --- | --- |
| `category_code` | `code` | Stable key, non-localized, unique. |
| `legacy_code` | `legacy_code` | Optional, non-localized. |
| `is_active` | `is_active` | Non-localized. |
| `sort_order` | `sort_order` | Non-localized, unique. |
| `name_en` | `name` | Default locale. |
| `description_en` | `description` | Default locale. |
| `name_hi_IN` | `name` | `hi-IN` localization. |
| `description_hi_IN` | `description` | `hi-IN` localization. |
| `desired_status` | ignored | Always publish. |

### Subject

| Artifact field | Strapi field | Notes |
| --- | --- | --- |
| `subject_code` | `code` | Stable key, non-localized, unique. |
| `legacy_code` | `legacy_code` | Optional, non-localized. |
| `is_active` | `is_active` | Non-localized. |
| `sort_order` | `sort_order` | Non-localized, unique. |
| `category_code` | `category` | Resolve to Category `documentId` by Category `code`. |
| `name_en` | `name` | Default locale. |
| `description_en` | `description` | Default locale. |
| `name_hi_IN` | `name` | `hi-IN` localization. |
| `description_hi_IN` | `description` | `hi-IN` localization. |
| `from_date` | `from_date` | Optional date field to add to Subject schema. |
| `to_date` | `to_date` | Optional date field to add to Subject schema. |
| `prabodhan_count` | `prabodhan_count` | Optional integer field to add to Subject schema. |
| `desired_status` | ignored | Always publish. |

## Multi-Stage Implementation Plan

Each stage below is intended to be small enough to become one GitHub issue and
to be completed in a single focused implementation pass.

### Stage 1 - Strapi Subject Schema Readiness

Goal: make the existing Strapi Subject Collection Type capable of storing all
Subject artifact fields needed for ingestion.

Scope:

1. Add optional Subject fields:
   - `from_date` with type `date`;
   - `to_date` with type `date`;
   - `prabodhan_count` with type `integer`.
2. Preserve existing Subject schema behavior:
   - `draftAndPublish: true`;
   - i18n enabled at the content-type level;
   - `code`, `legacy_code`, `is_active`, `sort_order`, `category`, and any new
     non-translation metadata fields set as non-localized.
3. Confirm Category and Subject `name` and `description` remain localized.
4. Confirm Category and Subject API route/controller/service files exist for
   REST ingestion.
5. Update schema documentation if schema ownership or field expectations change.

Defensive checks:

- Run JSON validation on the modified Strapi schema files.
- Run the CMS build command documented in the CMS README.
- Start the CMS against a disposable local database when available and confirm
  Strapi boots with the new schema.
- Do not ingest data in this stage.

Expected output:

- Subject schema can store every non-glossary field in the Subject artifact.
- No seed-data writer exists yet.

### Stage 2 - Ingestion CLI Foundation And Strapi Client

Goal: add a safe ingestion command foundation without performing writes by
default.

Scope:

1. Add a seed-data ingestion command group under `tools/seed-data`.
2. Read Category and Subject artifacts from their reviewed artifact locations.
3. Load Strapi API configuration from environment variables or explicit CLI
   options without committing secrets.
4. Implement a Strapi REST client wrapper for:
   - authenticated requests;
   - collection queries with filters;
   - create/update operations;
   - publish operations;
   - locale-aware reads/writes;
   - structured error reporting.
5. Add command-level modes:
   - dry-run by default;
   - explicit apply mode for writes.
6. Add shared report output summarizing:
   - records to create;
   - records to update;
   - records already matching;
   - conflicts;
   - blocked records;
   - skipped fields;
   - publish actions.
7. Add a read-only preflight check for:
   - Strapi API reachability;
   - authenticated access to Category and Subject endpoints;
   - default locale suitability for English fields;
   - `hi-IN` locale availability;
   - Draft & Publish support for Category and Subject.

Defensive checks:

- Unit-test artifact loading and environment/config validation.
- Unit-test that dry-run mode cannot write.
- Unit-test that apply mode requires an explicit flag.
- Unit-test preflight failures before any write planning.
- Mock Strapi responses for client behavior.

Expected output:

- A command skeleton that can inspect artifacts and Strapi, but does not yet
  apply Category or Subject writes.

### Stage 3 - Category Adapter, Dry-Run, And Apply

Goal: ingest Category records safely before Subject ingestion depends on them.

Scope:

1. Implement the Category adapter with the mapping recorded in this task.
2. Query existing Category records by stable `code`.
3. Treat missing Category records as creates.
4. Treat matching Category records as updates when updateable fields differ.
5. Report conflicts for:
   - duplicate existing Category records with the same `code`;
   - duplicate existing `sort_order` values that would block writes;
   - missing required artifact values;
   - missing required Strapi fields;
   - default locale not suitable for English fields;
   - missing `hi-IN` locale support.
6. Create or update the default locale record from English fields.
7. Create or update the `hi-IN` localization from Hindi fields.
8. Publish every Category record after successful create/update.
9. Ignore artifact `desired_status`.

Defensive checks:

- Unit-test Category field mapping.
- Unit-test dry-run create/update/conflict classification.
- Unit-test publish intent regardless of `desired_status`.
- Integration-test against a disposable Strapi instance when credentials and a
  clean local database are available.
- Verify the final dry-run after apply reports no pending changes.

Expected output:

- Categories can be ingested repeatedly without duplicates.
- Category `code` to Strapi `documentId` lookup is reliable for Subject
  ingestion.

### Stage 4 - Subject Adapter, Relation Resolution, Dry-Run, And Apply

Goal: ingest Subject records only after Category ingestion can provide stable
relationship targets.

Scope:

1. Implement the Subject adapter with the mapping recorded in this task.
2. Query existing Subject records by stable `code`.
3. Build a Category lookup by querying Categories by `code` and recording their
   Strapi `documentId` values.
4. Resolve every Subject `category_code` to a Category `documentId` before
   write planning.
5. Block Subject writes when any referenced Category is missing or ambiguous.
6. Treat missing Subject records as creates.
7. Treat matching Subject records as updates when updateable fields or the
   Category relation differ.
8. Create or update the default locale record from English fields.
9. Create or update the `hi-IN` localization from Hindi fields.
10. Set or update the `category` relation.
11. Publish every Subject record after successful create/update.
12. Ignore artifact `desired_status`.

Defensive checks:

- Unit-test Subject field mapping.
- Unit-test Category relation resolution by stable code.
- Unit-test unresolved/ambiguous Category blocking behavior.
- Unit-test dry-run create/update/conflict classification.
- Unit-test publish intent regardless of `desired_status`.
- Integration-test against a disposable Strapi instance after Stage 3 has
  ingested Categories.
- Verify the final dry-run after apply reports no pending changes.

Expected output:

- Subjects can be ingested repeatedly without duplicates.
- Every ingested Subject is linked to the intended Category.
- Subject date/count metadata is preserved in Strapi.

### Stage 5 - End-To-End Verification And Recovery Guidance

Goal: document and verify the complete operational path for maintainers.

Scope:

1. Add maintainer-facing documentation for:
   - required environment variables;
   - expected Strapi API token permissions;
- required locales;
- default locale expectation for English content;
   - clean local database recommendation;
   - dry-run commands;
   - apply commands;
   - expected report sections.
2. Add an end-to-end checklist:
   - validate Category artifact;
   - validate Subject artifact;
   - build CMS;
   - start CMS;
   - run Category dry-run;
   - apply Category ingestion;
   - run Category dry-run again;
   - run Subject dry-run;
   - apply Subject ingestion;
   - run Subject dry-run again;
   - inspect Strapi Admin for published English and Hindi localized entries.
3. Document recovery actions:
   - dry-run conflict: fix source artifact or Strapi trial data before apply;
   - failed Category apply: stop before Subject apply and rerun Category dry-run;
   - failed Subject apply: rerun Subject dry-run after Category relations are
     confirmed;
   - wrong field mapping discovered before apply: fix adapter and rerun dry-run;
   - wrong field mapping discovered after apply: update by stable `code` after
     a dry-run report, not by direct database edits;
   - local trial data contamination: clean local tables or database only after
     backup and only outside production environments.
4. Record any Strapi-specific operational limitations discovered during
   integration testing.

Defensive checks:

- Run all unit tests for seed-data tooling.
- Run CMS build.
- Run documented dry-run commands.
- Run apply commands only against an approved local or staging Strapi instance.
- Confirm repeated apply is idempotent by running dry-run after apply.

Expected output:

- Maintainers can operate the ingestion workflow without clicking through
  Strapi Admin for every Category and Subject.
- The workflow is repeatable, reviewable, and recoverable.

## Out Of Scope

- Glossary Collection Type creation.
- Glossary ingestion.
- Direct database writes.
- Frontend consumption behavior.
- RAG, metadata generation, or embedding updates.
- Automatic deletion of CMS records that are absent from artifacts.
- Production execution without a separate production readiness decision.

## Acceptance Criteria

- The plan is split into issue-sized stages.
- Category and Subject ingestion adapters are explicitly required.
- Dry-run is required before live writes.
- Field mapping is explicit and reviewed before implementation.
- Subject-to-Category relation resolution is based on stable Category codes.
- Subject schema additions are identified before Subject ingestion.
- English default locale and `hi-IN` localization behavior are specified.
- All ingested Category and Subject records are published regardless of
  artifact `desired_status`.
- Glossary work is clearly deferred.

## Execution Results

- 2026-07-11: Stage 1 implementation started under GitHub issue
  [#51](https://github.com/Team-Gurubodh/gurubodh/issues/51).
  - Added optional non-localized Subject fields:
    - `from_date` as a Strapi `date`;
    - `to_date` as a Strapi `date`;
    - `prabodhan_count` as a Strapi `integer`.
  - Confirmed Category and Subject `name` and `description` remain localized.
  - Confirmed Category and Subject route/controller/service files exist for
    REST ingestion.
  - Ran Strapi schema JSON validation, Stage 1 schema assertions,
    `git diff --check`, and `make cms-build`.
  - Booted Strapi successfully against the throwaway local PostgreSQL database
    `gurubodh_db_copy`; confirmed the `subjects` table has `from_date`,
    `to_date`, and `prabodhan_count` columns.
- 2026-07-11: Stage 2 implementation started under GitHub issue
  [#53](https://github.com/Team-Gurubodh/gurubodh/issues/53).
  - Added a seed-data `ingest` command group with read-only `preflight` and
    dry-run-default `plan` commands.
  - Added artifact loading for reviewed Category and Subject JSON artifacts.
  - Added Strapi API configuration from CLI options or environment variables:
    `GURUBODH_STRAPI_URL` and `GURUBODH_STRAPI_API_TOKEN`.
  - Added a Strapi REST client foundation for authenticated collection reads,
    create/update wrappers, locale-aware writes, and publish-by-status wrapper.
  - Added read-only preflight checks for Category and Subject endpoint access,
    expected locales, and Draft & Publish status queries.
  - Added Stage 2 report output with create/update/matching/conflict/blocked/
    skipped/publish sections while intentionally blocking adapter writes until
    later stages.
  - Added unit tests for artifact loading, config validation, dry-run write
    blocking, explicit apply mode, mocked Strapi client behavior, and preflight
    locale failures.
- 2026-07-11: Stage 3 implementation started under GitHub issue
  [#55](https://github.com/Team-Gurubodh/gurubodh/issues/55).
  - Added Category ingestion planning by stable `code`.
  - Added explicit Category field mapping for English default-locale payloads
    and `hi-IN` localized payloads.
  - Added dry-run classification for creates, updates, matching records, and
    conflicts.
  - Added apply behavior for Category default-locale writes, Hindi
    localization writes, and publish-on-write behavior.
  - Kept Subject ingestion blocked until Stage 4.
  - Confirmed Strapi 5 localization writes for this app use
    `PUT /api/categories/{documentId}?locale=hi-IN&status=published`.
  - Ran the seed-data unit test suite, `git diff --check`, Category dry-run,
    Category apply against the throwaway Strapi database, and final Category
    dry-run idempotency verification.
  - Final Category dry-run after apply reported 11 matching Category records,
    0 creates, 0 updates, 0 conflicts, and 0 publish actions.

## Follow-Up

- Create separate GitHub issues for each stage when implementation begins.
- Revisit Glossary Collection Type creation and ingestion only after Category
  and Subject ingestion is proven.
