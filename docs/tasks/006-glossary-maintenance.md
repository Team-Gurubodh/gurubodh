# Task-006: Maintain Glossary of Philosophical Terms - Phase 1

<record_type>task_history</record_type>
<status>started</status>
<date>2026-06-27</date>
<owners>Gurubodh maintainers</owners>

## Goal
- Maintain a glossary of philosophical terms in Google Sheets
- The Google Sheet will have the following columns
  - Sr No
  - Term Code
  - Term
  - Definition
- The column `Term Code` should validate the code to be of this format: `Tnnnnn`, where the first character is always `T` and the `nnnnn` stands for a number ranging from `00001` to `50000`.
- Following columns should have conditional formatting to prevent duplicate entries within the same column
  - Term
- A new directory named `seed-data` should be created under directory `tools/`
- It should have a `README.md` with the link to the Google Sheet where the glossary is being maintained together with explanation of what that document does. The `README.md` should include information recorded under this documents Context and Decision Sections so that user can understand the motive and usage behind this effort.
- The Glossary will be downloaded manually in `CSV` format into this directory for further processing.
- We need to develop a tool to convert The Glossary to `JSON` format for ingestion into `Strapi 5 CMS`. The `JSON` format should be compatible to `GlossaryTerm` content type within `Strapi 5` 
- The objective is to prepare Glossary of Philosophical Terms as seed-data that will be used for searching and matching within the application to be developed over the Strapi CMS application 
- We need to develop a tool to ingest `JSON` compatible with `GlossaryTerm` content type as seed-data via Strapi 5 API or any alternative, but better approach.

## Context
When Gurubodh UI is released, in the early version, we may make use of Typically used Glossary of Philosophical Terms for searching for a topic. The exact way in which these terms is to be used is will not be fully known till the UI is developed. But it is known that these terms will be extremely useful for adding meaningful tags to each Gurubodh chapter within the CMS. This is likely to be very similar to a classic dictionary-based entity tagging problem (sometimes called gazetteer matching). When matching results are found it is still not clear as to whether we should store results as per-lecture JSON or a reverse index (term → [lecture_ids]) for search/filtering later.

## Decisions
- We need to develop a strategy and tooling to accomplish the goals above.
- Semantic matching should be considered, but this might get into the domain of vector DB and RAG, and therefore may be considered for later implementation. 

## My response to proposed plan
1. The proposed change two boundaries, first being the glossary preparation under `tools/glossary`. Actually glossary is going to be one of the three seed-data types that I was contemplating on preparing for the Strapi CMS and Strapi App to work on. Other than `glossary`, I was thinking of contemplating on creating seed-data ingestion for the `Subject` and `Category` content types. As such, I wonder if we should design a more generic seed-data ingestion tool.
2. My other thought around a more generic seed-data ingestion tool was that I have read on the internet that Strapi 5 itself has an already defined way and route to get seed-data ready. As such, I want you to contrast generic seed-data tool development based on python vs Strapi's own solution to deal with seed-data. Please compare and contrast these two option and recommend a way forward.
3. I fixed the typo with the task: "Sr No should validate the term code". Please confirm.

## My second response to proposed plan
1. I like the idea: Build `tools/seed-data` as the canonical seed-data preparation and ingestion tool.
2. One primary reason for Glossary to be maintained externally in a Google Sheet is that other experts in the domain of Sanatana Dharma or other volunteers can contribute without having to know Strapi based new User Interface. Spreadsheets are common and easy to use.
3. I wnat to confirm that when we ingest seed data using Strapi 5's APIs, Strapi is capable of generating necessary internal IDs. In other words, by bypassing Strapi's own seed-data ingestion, we are not creating a new problems such as non-native strapi content type and such.
4. My final response is around tools crossing boundaries... Given the project architecture, it is necessary now to consider Interface Control Documents? 

## My third response to proposed plan
- Why do you think that it is now time to introduce lightweight Interface Control Documents (ICDs)? Please respond with full understanding of the overall architecture, your assessment of the complexity of this project or the lack of it, as well as after considering alternatives to ICDs or after considering how absence of ICDs may impact the project negatively. 

## Modifications to Plan
- I am dropping the following columns from Google Sheets where I am planing to maintain the Glossary
  - English Term
  - English Definition
  - Category
- I will maintain two glossaries first one is called "Sanatan Glossary" and the other called "Prabodhan Glossary". Both will become seed-data for tagging the content in Stapi CMS
- I am thinking of two different ways in which I will use these Glossaries. One is tagging chapters with matching Glossary term. The other one is likely to be used as "Content Descriptor" - a name-value pair inside the metadata JSON.
- In any case, both these become part of Strapi as seed-data.


## Approved Plan

1. Treat glossary maintenance as the first use case of a broader seed-data
   workflow.
   - Create a canonical seed-data tooling boundary under `tools/seed-data`
     instead of creating a one-off `tools/glossary` implementation.
   - Keep glossary-specific CSV handling as the first implemented workflow
     inside that tool.
   - Support more than one glossary source from the beginning, starting with
     `Sanatan Glossary` and `Prabodhan Glossary`.
   - Design the tool so `category`, `subject`, and `glossary-term` seed-data
     workflows can be added incrementally without redesigning the boundary.

2. Keep the external Google Sheet workflow for glossary authors.
   - Use Google Sheets because domain experts and volunteers can contribute
     glossary terms without needing to learn Strapi or use the Strapi admin UI.
   - Keep the spreadsheet columns defined in this task:
     `Sr No`, `Term Code`, `Term`, and `Definition`.
   - Maintain `Sanatan Glossary` and `Prabodhan Glossary` as separate glossary
     sources, while allowing both to flow through the same seed-data validation,
     JSON generation, and Strapi ingestion workflow.
   - Use Google Sheets validation for `Term Code` in the `Tnnnnn` format, where
     the numeric range is `00001` through `50000`.
   - Use Google Sheets conditional formatting to highlight duplicate values in
     `Term`.
   - Treat spreadsheet validation and formatting as human-entry guidance; the
     seed-data tool must still perform repeatable validation before generating
     or ingesting artifacts.

3. Define Strapi CMS content-type requirements before implementing ingestion.
   - Confirm or create the `GlossaryTerm` Strapi 5 content type before the
     ingestion command is finalized.
   - Keep the stable business identifier as `code`, using values such as
     `T00001`.
   - Do not use Strapi-generated internal identifiers as source-data keys.
   - Let Strapi generate its native internal `id` and Strapi 5 `documentId`
     through its normal API behavior.
   - Decide whether `Sanatan Glossary` and `Prabodhan Glossary` should be
     represented as:
     - a single `GlossaryTerm` content type with a required glossary/source
       discriminator field; or
     - separate content types only if their schemas or lifecycle rules diverge
       meaningfully.
   - Prefer a single content type with an explicit glossary/source field unless
     Strapi content-model review shows a strong reason to separate them.

4. Use Strapi REST APIs for seed-data ingestion.
   - Ingest seed data through Strapi's Content API instead of direct database
     writes.
   - Prefer REST for server-to-server writes, consistent with the current
     recommended direction in ADR-0004.
   - Treat Strapi's built-in data import/export/transfer capabilities as useful
     for environment movement or Strapi-managed data operations, not as the
     primary workflow for volunteer-maintained spreadsheet seed data.
   - Make ingestion idempotent by looking up records through stable `code`
     values, creating missing records, and updating existing records where
     appropriate.
   - If two glossary sources share the same `Term Code` format, make the
     idempotency key either globally unique `code` or a documented composite of
     glossary/source plus `code`, depending on the final CMS content model.
   - Include a dry-run mode before live writes.

5. Build a staged seed-data artifact workflow.
   - Convert manually downloaded glossary CSV files into reviewed JSON
     artifacts.
   - Store generated artifacts in a predictable location under `tools/seed-data`
     so they can be inspected before ingestion.
   - Keep the JSON shape compatible with the Strapi content type, but avoid
     embedding Strapi-generated identifiers in the source artifact.
   - Validate required headers, required fields, code format/range, duplicate
     glossary terms within each glossary source, and malformed rows.
   - Include the glossary source identity in the generated artifact so
     downstream ingestion and future metadata-generation workflows can
     distinguish `Sanatan Glossary` from `Prabodhan Glossary`.
   - Produce clear validation errors that a maintainer can map back to the
     spreadsheet row.

6. Introduce a lightweight interface document for seed-data artifacts.
   - Create `docs/interfaces/` as the documentation home for component-boundary
     interface records.
   - Start with a concise seed-data interface document, likely
     `docs/interfaces/seed-data-artifacts.md`.
   - Define the contract between external source files, `tools/seed-data`, JSON
     staging artifacts, and the Strapi CMS API.
   - Include source columns, supported glossary sources, generated JSON shape,
     stable keys, validation rules, endpoint mapping, idempotency behavior, and
     the rule that Strapi internal IDs are generated by Strapi and not supplied
     by the seed-data tool.
   - Keep this lightweight and practical; do not introduce a heavy formal ICD
     process for the whole project yet.

7. Update project documentation alongside implementation.
   - Update `docs/README.md` so `docs/interfaces/` is discoverable.
   - Update `docs/schemas.md` if new schema locations or Strapi content types
     are added.
   - Add `tools/seed-data/README.md` explaining the seed-data workflow, Google
     Sheet usage, manual CSV download, validation, JSON generation, and Strapi
     ingestion.
   - Record the Google Sheet link in the seed-data README once it is available.
   - Preserve the architecture rule that the CMS is the system of record after
     successful ingestion.

8. Defer semantic matching and RAG-specific behavior.
   - Treat both glossaries as authoritative seed data in Phase 1.
   - Do not implement vector search, semantic matching, reverse indexes, or
     per-lecture tagging as part of this task.
   - Keep future matching approaches open, including classic gazetteer matching
     for chapter tagging, name-value `Content Descriptor` metadata, generated
     metadata, reverse indexes, and later vector/RAG workflows.

9. Verify in small increments.
   - Verify the seed-data CLI can show help and validate sample glossary input.
   - Verify CSV-to-JSON conversion produces stable, reviewable output.
   - Verify CMS changes with the documented CMS build command when content
     types are added.
   - Verify live ingestion only when a Strapi instance and appropriate API token
     are available; otherwise record exactly what was skipped and why.

## Execution Results

### State Summary - 2026-07-01

#### What Was Built
- Created the canonical seed-data tooling boundary under `tools/seed-data`.
- Added a Python package named `gurubodh-seed-data` with the console command
  `gurubodh-seed-data`.
- Added the initial top-level seed-data workflows:
  - `glossary` - scaffolded
  - `category` - planned
  - `subject` - planned
- Added the first glossary sources:
  - `sanatan-glossary` - Sanatan Glossary
  - `prabodhan-glossary` - Prabodhan Glossary
- Added canonical local file-location provisions for glossary input/output:
  - `sources/glossary/sanatan-glossary.csv`
  - `sources/glossary/prabodhan-glossary.csv`
  - `artifacts/glossary/sanatan-glossary.json`
  - `artifacts/glossary/prabodhan-glossary.json`
- Added source-key validation for glossary path lookup. Unsupported source keys
  fail with accepted values listed.
- Added `tools/seed-data/README.md` with setup, command, and local file-location
  guidance.
- Updated the top-level `README.md` to include `tools/seed-data` in the project
  map.
- Updated `.gitignore` so early-development local seed-data CSV sources and JSON
  artifacts are not committed:
  - `tools/seed-data/sources/`
  - `tools/seed-data/artifacts/`
- Merged PR #16, `chore(seed-data): scaffold glossary workflow`, into `main`.
  This brought in both the task-history record and the seed-data scaffold.

#### What Works
- `gurubodh-seed-data workflows` lists scaffolded and planned seed-data
  workflows.
- `gurubodh-seed-data glossary sources` lists the two glossary sources without
  premature Strapi content-type assumptions.
- `gurubodh-seed-data glossary paths` displays canonical CSV input and JSON
  artifact output paths for both glossary sources.
- `gurubodh-seed-data glossary paths --source sanatan-glossary` filters to the
  Sanatan Glossary source.
- `gurubodh-seed-data glossary paths --source prabodhan-glossary` filters to the
  Prabodhan Glossary source.
- `gurubodh-seed-data glossary paths --source wrong-name` fails with exit code
  `2` and reports:
  `Accepted values: sanatan-glossary, prabodhan-glossary`.
- Python syntax verification passed with:
  `python3 -m compileall tools/seed-data/gurubodh_seed_data`.
- Local downloaded glossary CSV files are present but ignored by git. Their
  current headers were confirmed as:
  `Sr No,Term Code,Term,Definition`.
- Local `main` was fast-forwarded after PR #16 was merged, and the local and
  remote feature branches were cleaned up.

#### Important Clarifications
- `glossary` is the seed-data workflow. `sanatan-glossary` and
  `prabodhan-glossary` are glossary sources handled by that workflow.
- There is currently no Strapi content type named `glossary-term` in the repo.
  The seed-data scaffold intentionally no longer exposes a `Content Type` column
  for glossary sources.
- The final Strapi content model is still undecided. The likely direction is one
  collection type with an explicit glossary/source field unless later CMS review
  shows a strong reason to separate the two glossaries.
- Google Sheets remains the authoring interface for now. Git-tracked CSV source
  snapshots are deferred because the glossary data is still expected to change
  frequently during early development.
- Generated JSON artifacts are also ignored for now and will be regenerated once
  the conversion workflow exists.
- GitHub CLI authentication is valid in the user's normal shell, but not in the
  Codex command environment. Git over SSH works from Codex, so Codex can still
  push, fetch, pull, and clean branches; PR creation/inspection is currently best
  handled through VS Code or GitHub UI.

## Follow-Up

### Next Logical Chunk: Glossary CSV Validation
- Create a new branch from updated `main` for the next slice of issue #11.
- Add a validation command, likely:
  `gurubodh-seed-data glossary validate --source sanatan-glossary`
  and
  `gurubodh-seed-data glossary validate --source prabodhan-glossary`.
- The validation command should read the canonical CSV path from the source key.
- Validate CSV content only; do not generate JSON in this chunk.
- Initial validation rules should include:
  - required headers: `Sr No`, `Term Code`, `Term`, `Definition`
  - required field values
  - `Term Code` format and range: `T00001` through `T50000`
  - duplicate `Term` values within the same glossary source
  - malformed or blank rows
  - row-numbered error messages that can be mapped back to the spreadsheet
- Decide how to handle leading/trailing whitespace in CSV values. The local
  `prabodhan-glossary.csv` currently has visible trailing spaces in some values,
  so the validator should either trim values before validation or report
  whitespace issues clearly.
- After CSV validation, the following chunk should be CSV-to-JSON artifact
  generation under `tools/seed-data/artifacts/glossary/`.
