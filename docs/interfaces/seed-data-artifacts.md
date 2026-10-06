# Seed-Data Artifact Interface

<record_type>interface_contract</record_type>
<status>accepted</status>
<date>2026-07-07</date>
<owners>Gurubodh maintainers</owners>

## Boundary

External CSVs → seed-data CLI → validated JSON artifacts → Strapi 5 REST API.
Generation is deterministic and offline; it must not require a running CMS.
Target compatibility checks and API writes belong to ingestion.

Sources and artifact destinations are configured in
[seed_data_sources.json](../../tools/seed-data-cli/config/seed_data_sources.json).
Paths are configuration, not a maintainer-specific filesystem contract.
Artifacts are reviewable staging data, separate from CMS content-type schemas.
They exclude native `id`, `documentId`, relation IDs, internal timestamps, and
created/updated user fields. Strapi owns those values.

## Schema and adapter entry points

Schemas own exhaustive fields, envelopes, types, and structural constraints.
Adapters own explicit artifact-to-CMS payload mappings.

| Type | Artifact schema | CMS schema | Ingestion adapter |
| --- | --- | --- | --- |
| Category | [Category artifact](../../tools/seed-data-cli/config/category_artifact.schema.json) | [Category](../../apps/gurubodh-cms/src/api/category/content-types/category/schema.json) | [category_ingestion.py](../../tools/seed-data-cli/gurubodh_seed_data/category_ingestion.py) |
| Subject | [Subject artifact](../../tools/seed-data-cli/config/subject_artifact.schema.json) | [Subject](../../apps/gurubodh-cms/src/api/subject/content-types/subject/schema.json) | [subject_ingestion.py](../../tools/seed-data-cli/gurubodh_seed_data/subject_ingestion.py) |
| Sanatan Glossary | [Glossary artifact](../../tools/seed-data-cli/config/glossary_artifact.schema.json) | [Sanatan Glossary](../../apps/gurubodh-cms/src/api/sanatan-glossary/content-types/sanatan-glossary/schema.json) | [glossary_ingestion.py](../../tools/seed-data-cli/gurubodh_seed_data/glossary_ingestion.py) |
| Prabodhan Glossary | Same glossary artifact schema | [Prabodhan Glossary](../../apps/gurubodh-cms/src/api/prabodhan-glossary/content-types/prabodhan-glossary/schema.json) | Same glossary adapter, separate target |

## Identity and locales

Reconciliation uses business keys, not artifact-supplied CMS IDs:

- Category `category_code` maps to CMS `code`.
- Subject `subject_code` maps to CMS `code`; `category_code` identifies its parent.
- Glossary `term_code` maps to CMS `code` within the selected glossary collection.
  The same term code may occur in the other glossary.

These codes persist across display-text edits. Category/Subject codes are shared
across CMS localizations. `documentId` identifies the document in the target CMS
for updates and relations; another CMS database need not preserve it.

Category and Subject map `name_en` / `description_en` to default English (`en`)
and `name_hi_IN` / `description_hi_IN` to Hindi (`hi-IN`). The Hindi CSV headers
use `hi-IN`; artifacts use `hi_IN`. Ingestion preflight requires the configured
default and localized locales. This is display localization, not Marathi or
Hindi prepared-chapter ingestion.

Both glossaries are non-localized collections with Draft & Publish enabled.
There are no chapter relationships or automatic term assignment in this contract.

## Validation responsibilities

The [CSV validator](../../tools/seed-data-cli/gurubodh_seed_data/validation.py)
checks required header order, values, business-key formats, duplicates within
each source, and Subject references against the Category source. Spreadsheet
validation is entry-time guidance and cannot replace tooling validation.
Errors should identify the source row and field; failed validation prevents
artifact writing.

Generation validates the artifact shape. Ingestion independently validates
artifact schemas and target identity, then checks CMS endpoint access and
compatibility. The [target ingestion boundary](../../tools/seed-data-cli/gurubodh_seed_data/target_ingestion.py)
plans creates, updates, conflicts, and blocked records. It must not silently
choose among duplicate business keys or ambiguous parent relations.

## Apply behavior and dependencies

`ingest preflight`, `ingest plan`, and `ingest apply` are implemented for all
four targets. Use the [ingestion guide](../../tools/seed-data-cli/README.md#strapi-ingestion-workflow)
for commands, authentication, reports, and recovery; use the
[glossary guide](../../tools/seed-data-cli/README.md#glossary-strapi-ingestion-workflow)
for glossary-specific operations.

Apply Category and Subject in separate invocations. Required Categories must
exist before dependent Subjects can be applied; Category apply does not trigger
Subject apply. Subject ingestion resolves the business `category_code` to a
Category `documentId` and blocks missing or ambiguous relationships.

Category and Subject artifacts retain `desired_status`, but their implemented
adapters ignore it and publish created or updated records, including when its
value is `draft`. Reports identify it as skipped. Consumers must not interpret
this field as a supported draft-publication control. Publication behavior is
implemented in the adapters, not inferred from artifact schema enums.

## Open scope

Collection-specific glossary extensions need a future schema/contract decision;
no additional fields are implied by this shared contract. The editorial rule
for assigning a term to one glossary remains open in
[#353](https://github.com/Team-Gurubodh/gurubodh/issues/353).
Whether artifacts are committed or regenerated as local outputs remains an
open repository-data policy choice.
