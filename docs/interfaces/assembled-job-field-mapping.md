# Assembled job field mapping

This is S4's exhaustive reconciliation for [#283](https://github.com/Team-Gurubodh/gurubodh/issues/283),
approved in [#298](https://github.com/Team-Gurubodh/gurubodh/issues/298).
It specifies assembly obligations for #284; production loading/composition is
not implemented by this record or its fixture tests.

The owning contracts remain [S1 / Decision-0009](../decisions/0009-cli-execution-profile-contracts.md),
[S2 / Decision-0010](../decisions/0010-cli-manifest-locale-contracts.md), and
[S3 / #296](https://github.com/Team-Gurubodh/gurubodh/issues/296#interface-contract--approved).
S3's exact command/environment/storage declarations and handoff stay in #296
under the maintainer's documentation exception. This record reconciles their
assembled destinations; it does not replace those declarations.

## Reading the mapping

`prep`, `chunks`, and `docx` mean prep-subject **1.5.0**, generate-chunks
**1.2.0**, and generate-docx **1.0.0**. Paths describe assembled JSON, including
object containers and array items (`[]`). Each command/path has exactly one
row; tests compare this inventory against the unchanged job definition schemas.
Multiple paths in a row share the same owner and presence rule.

The selected edition is the manifest entry for the selected supported locale.
An artifact location means prep destination or chunks/DOCX source/destination.
Selected stores are determined by the command roles and storage-profile bindings
defined in S3. `Required` below means explicit in composed output, even where a
legacy job schema permits omission. All construction is field by field: no deep
merge, interpolation, includes, arbitrary overrides, or per-subject thin jobs.

## Complete assembled field inventory

| Commands | Field | Owner / construction | Presence / compatibility |
| --- | --- | --- | --- |
| prep,chunks,docx | `$` | Resolver constructs the command-specific object from validated components | Required; only the fields below enter the job |
| prep,chunks,docx | `$.schema_version` | Command `job_schema_version` | Required; prep 1.5.0, chunks 1.2.0, DOCX 1.0.0 |
| prep,chunks,docx | `$.pipeline` | Command fixed pipeline; prep indexes `pipeline_by_encoding` with edition encoding | Required; APS selects legacy-docx-to-unicode, Unicode selects unicode-docx-ingest |
| prep,chunks,docx | `$.source`, `$.destination` | Resolver constructs the selected store's applicable location shape using S3 roles | Required; local and R2 shapes use only their applicable fields |
| prep,chunks,docx | `$.source.backend`, `$.destination.backend` | Selected environment store `backend` | Required; legacy prep may omit it and interpret local |
| prep,chunks,docx | `$.source.root_dir`, `$.destination.root_dir` | Selected local store's named `$env` binding, resolved by #284 | Required for local; omitted for R2; used value must be a nonempty absolute path |
| prep,chunks,docx | `$.source.bucket`, `$.destination.bucket` | Selected R2 store `bucket` | Required for R2; omitted for local |
| prep,chunks,docx | `$.source.url_base`, `$.destination.url_base` | Selected R2 store `url_base`, including explicit null | Required for R2; omitted for local; legacy prep may omit it |
| prep | `$.source.relative_path` | Edition `source_document.relative_path` | Required for local DOCX source; omitted for R2 |
| prep | `$.source.key` | Selected R2 source-store prefix + slash + edition source-relative path | Required for R2 DOCX source; omitted for local; prefix is consumed into key |
| prep | `$.source.font_encoding`, `$.source.file_format` | Same-named edition `source_document` fields | Required for either backend; aps/unicode and docx; actual font inspection remains execution work |
| prep,chunks,docx | `$.destination.prefix` | Selected R2 destination-store `prefix` | Required for R2; omitted for local |
| chunks,docx | `$.source.prefix` | Selected R2 source-store `prefix` | Required for R2; omitted for local |
| prep,chunks,docx | `$.destination.subject_dir` | Manifest `artifact_root` + slash + selected locale | Required; never inferred from manifest ID, directory, subject code, or slug |
| chunks,docx | `$.source.subject_dir` | Manifest `artifact_root` + slash + selected locale | Required; must equal destination subject_dir |
| prep,chunks,docx | `$.naming` | Resolver constructs only command `naming_fields` from identity/release/locale owners | Required; field order does not change filename formatting |
| prep,chunks,docx | `$.naming.category_code`, `$.naming.subject_code`, `$.naming.title_slug` | Same-named manifest `identity` fields | Required for all canonical commands |
| prep,chunks | `$.naming.version`, `$.naming.subversion` | Same-named selected edition `release` fields | Required strings retaining leading zeroes; independent per locale; absent from DOCX naming |
| chunks,docx | `$.naming.language` | Selected locale, matching the manifest edition and locale definition | Required; prep puts language in metadata instead |
| prep | `$.chapter_split` | Selected edition `chapter_split` shape | Required; only active shape fields are copied |
| prep | `$.chapter_split.enabled` | Edition split `enabled` | Required boolean; false produces only this field |
| prep | `$.chapter_split.pattern_type`, `$.chapter_split.pattern` | Same-named edition split fields | Required when enabled; omitted when disabled |
| prep | `$.chapter_split.flags`, `$.chapter_split.flags[]` | Edition regex split's explicit flags array and each declared flag | Required for regex, including empty array; omitted for literal/disabled; legacy regex jobs may omit flags |
| prep | `$.metadata_defaults` | Resolver constructs declared locale metadata plus selected language | Required; no arbitrary metadata extension in composition |
| prep | `$.metadata_defaults.language` | Selected locale, matching edition and locale definition | Required; hi-IN or mr-IN; no independent language override |
| prep | `$.metadata_defaults.source_script`, `$.metadata_defaults.output_text_encoding` | Same-named locale metadata fields | Required explicit Devanagari and UTF-8 declarations |
| prep | `$.metadata_defaults.summary_chapter_markers`, `$.metadata_defaults.summary_chapter_markers[]` | Locale metadata marker array and each declared string | Required array, including empty; legacy complete jobs may omit the array |
| prep | `$.proofreading` | Complete selected proofreading profile's settings object | Required; profile identity/envelope does not enter job JSON |
| prep | `$.proofreading.enabled`, `$.proofreading.provider`, `$.proofreading.model`, `$.proofreading.max_output_tokens` | Same-named settings in selected proofreading profile (S1) | Every field required; no defaults or scalar merge |
| prep | `$.proofreading.max_input_characters`, `$.proofreading.max_retries`, `$.proofreading.initial_retry_delay_seconds`, `$.proofreading.max_retry_delay_seconds` | Same-named settings in selected proofreading profile (S1) | Every field required; no defaults or scalar merge |
| prep | `$.proofreading.min_request_interval_seconds`, `$.proofreading.max_requests_per_minute`, `$.proofreading.max_estimated_input_tokens_per_minute` | Same-named settings in selected proofreading profile (S1) | Every field required; no defaults or scalar merge |
| prep | `$.proofreading.request_timeout_seconds`, `$.proofreading.request_progress_interval_seconds` | Same-named settings in selected proofreading profile (S1) | Every field required; component semantics additionally require progress interval not above timeout |
| prep | `$.proofreading.unavailable_max_retries`, `$.proofreading.unavailable_first_retry_delay_seconds`, `$.proofreading.unavailable_second_retry_delay_seconds`, `$.proofreading.unavailable_cooldown_seconds`, `$.proofreading.continue_on_error` | Same-named settings in selected proofreading profile (S1) | Every field required, including explicit false; no defaults or scalar merge |
| chunks | `$.chunking` | Complete selected chunking profile's settings object | Required; profile identity/envelope does not enter job JSON |
| chunks | `$.chunking.provider`, `$.chunking.model`, `$.chunking.model_revision` | Same-named settings in selected chunking profile (S1) | Every field required; preserve maintained BGE-M3 model and pinned revision |
| chunks | `$.chunking.threshold_percentile`, `$.chunking.min_chars`, `$.chunking.window_size`, `$.chunking.batch_size` | Same-named settings in selected chunking profile (S1) | Every field required; preserve maintained values 78, 550, 3, and 16 |
| chunks | `$.chunking.normalize_contextual_vectors`, `$.chunking.device`, `$.chunking.local_files_only`, `$.chunking.strategy_version` | Same-named settings in selected chunking profile (S1) | Every field required, including nullable device and booleans; maintained true, null, true, semantic-window-v1 |
| chunks | `$.chapters`, `$.chapters[]` | Explicit invocation chapter list and its entries | Optional; absent means unspecified, not an injected list; supplied list is nonempty/unique with exactly three ASCII digits per string |

## Component fields used for construction and selection

The preceding table accounts for every copied setting. The following accounts
for component envelopes, containers, selection declarations, and values consumed
in derivation; these are not extra assembled fields.

| Component fields | Purpose and destination |
| --- | --- |
| All component roots and `component_schema_version` | Strict declaration envelopes; format 1.0.0 validation only, distinct from job schema version |
| Manifest `manifest_id` | Resource identity; never a naming/artifact-root fallback |
| Manifest `identity` and its three children | Group the naming values mapped above |
| Manifest `artifact_root` | Explicit input to artifact subject_dir construction |
| Manifest `editions`, its hi-IN/mr-IN keys, and edition objects | Select a complete independent locale edition; no inheritance between languages |
| Edition `release`, `source_document`, `chapter_split` and their children | Containers/values mapped above; source encoding also selects the prep pipeline |
| Manifest/edition `profile_overrides`, `.proofreading`, `.chunking` | Optional applicable whole-profile IDs; empty or omitted inherits the earlier selection |
| Locale `locale`, `metadata_defaults` and its children | Resource/edition correspondence and metadata values mapped above; no second language declaration |
| Command `command_id` | Resource identity and applicable command branch; lab has no canonical job |
| Command `job_schema_version`, `pipeline`, `pipeline_by_encoding`, `.aps`, `.unicode` | Choose the job version/pipeline mapped above; no implicit map entry |
| Command `source_role`, `destination_role` | Select storage-profile bindings; S3 owns exact declarations |
| Command `naming_fields` and entries | Select the exact naming set; values come from manifest/edition/locale |
| Command `default_profiles`, `.proofreading`, `.chunking` | JSON-owned starting selections; required empty object for DOCX; narrow lab binding selects proofreading |
| Environment `environment_id`, `stores`, and store keys/objects | Environment/resource and named-store selection; S3 owns declaration shapes |
| Store `backend`, `root_dir`, `root_dir.$env`, `bucket`, `prefix`, `url_base` | Location values mapped above; the environment reference is consumed, not copied; prep R2 source prefix becomes key |
| Storage profile `storage_profile_id`, `source_document`, `subject_artifact_source`, `subject_artifact_destination` | Resource identity and three role-to-store-ID selections; S3 owns routes |
| Execution profile `profile_id`, `proofreading`/`chunking` containers and all settings | ID selects one immutable policy; complete settings map above; component version and profile ID remain outside job JSON |

## Selection, lookup, and omission

For each applicable kind, precedence is **command-definition JSON → manifest
JSON → edition JSON → explicit profile argument for this run**. The last supplied
ID wins; an omitted key or empty override object retains the earlier selection.
The selected document must be complete even if an earlier one has a missing
setting. No individual settings are merged. A manifest may declare both kinds;
prep consumes proofreading, chunks consumes chunking, DOCX consumes neither.
Explicit inapplicable invocation selections fail future resolution rather than
being silently applied. Lab uses its narrow command binding without a manifest
or edition and stays non-canonical; CLI details remain #286.

For illustration, command `standard-v1`, manifest `careful-v1`, absent edition
override, and run argument `review-v1` selects all settings from `review-v1`.
Without the run argument it selects `careful-v1`. These illustrative IDs do not
create maintained profiles. Executable fixture examples cover all four levels,
absence/empty inheritance, and incomplete selected profiles. They characterize
the contract; they do not claim production precedence is implemented.

Maintained prep and lab command fixtures select `gemini-3.6-flash-v1`, model
`gemini-3.6-flash`, and 16,384 output tokens. Chunks selects
`bge-m3-semantic-window-v1`. Changing a used policy requires a new ID and explicit
selection; format version 1.0.0 does not identify policy content. Exact-input
hash auditing belongs to #285; validation cannot prove historical immutability.

Stable IDs select fixed directories under the CLI root:

| Resource | Fixed location |
| --- | --- |
| Manifest | `jobs/subjects/<manifest-id>/manifest.json` |
| Command | `config/job-components/commands/<command-id>.json` |
| Environment | `config/job-components/environments/<environment-id>.json` |
| Storage profile | `config/job-components/storage-profiles/<storage-profile-id>.json` |
| Locale | `config/job-components/locales/<locale>.json` |
| Proofreading / chunking profile | `config/job-components/profiles/<proofreading-or-chunking>/<profile-id>.json` |

#284 validates ID grammar before lookup, containment, resource existence, kind,
format version, and expected ID correspondence. No arbitrary file graph,
inheritance, path/URI IDs, or interpolation. `validate_component(..., path=...)`
uses path only as diagnostic context; the loader supplies `expected_id` explicitly.
Current fixtures represent these contracts but are not a production catalog.

## Validation and runtime boundaries

| Boundary | Checks / responsibilities |
| --- | --- |
| Component validation, delivered by S1–S3 | Independently owned Draft 2020-12 fields, types/bounds/shapes, unknown fields, safe paths/IDs/references, supported kinds/versions, explicit expected-ID matching, progress interval/timeout, and safe Python regex compilation using declared flags; returns None or ConfigurationError without mutation/defaults |
| Future resolution, #284 | Cross-resource checks and selection; only consumed store references and root variables resolve; nonempty absolute roots valid for the platform, no guessed base or tilde/embedded expansion; destination existence not required; explicit field construction and exact invocation chapter checks |
| Existing preparation APIs | Job-schema and locale/encoding/path invariants; language-qualified source/destination equality; proofreading maximum retry delay must be at least initial retry delay; runtime policy records and compiled regex stored separately; to_payload preserves schema-shaped JSON |
| Existing execution | Source/artifact availability, actual DOCX/font allowlist, provider access, model availability, storage I/O, canonical publication and derived-artifact readiness |

All supplied environment store declarations are structurally validated even if
unused. Only used bindings resolve; an R2-only command does not read unused
local roots. Missing/empty/invalid used variables or consumed store references
fail with component/field/variable-name diagnostics, without values. This used-root
behavior is a #284 obligation, not executed by S4's mapping fixtures.

The existing `GURUBODH_MODEL_CACHE_DIR`, `GEMINI_API_KEY`, and
`CLOUDFLARE_R2_ACCOUNT_ID`, `CLOUDFLARE_R2_ACCESS_KEY_ID`,
`CLOUDFLARE_R2_SECRET_ACCESS_KEY` retain their runtime handling. No credentials,
model-cache paths, compiled patterns, locale instruction templates, provider
objects, or resolved runtime records become new job properties. Execution flags
such as overwrite/resume likewise retain their command/runtime boundary.

Malformed component errors identify kind, supplied origin, safe JSON location,
and violated rule deterministically without rejected values or raw compiler/
provider/schema-library errors. Job errors remain ConfigurationError; generated
artifact validation remains ProcessingError. Component independence checks are
separate from assembled-job validation, which deliberately uses job schemas.

## Legacy allowances and retirement

Complete jobs retain their existing schemas and preparation behavior. Composition
uses the stricter explicit component declarations above:

- Prep source/destination backend omission still means local in legacy handling.
  Prep R2 url_base and regex flags may be absent in complete jobs. Existing schema
  default annotations do not inject JSON values; explicit component declarations
  supply composed values, including null, false, and empty arrays.
- Prep job schemas can accept inactive/mixed storage fields and disabled split
  pattern settings. Components reject those shapes; composition omits inactive
  fields. Optional complete-job summary markers remain supported without creating
  an omitted-marker component fallback.
- Prep `metadata_defaults` has an open additional-properties extension point.
  Those arbitrary keys have no component owner and are legacy-only input, not
  copied from a locale component. Acceptance alone does not promise a downstream
  effect for an unknown key. Additional metadata needs a separate change request.
- Complete-job regexes for identity/releases/chapter numbers can accept a final
  newline. Component identity/release patterns are exact; future invocation
  chapter strings must also be exact. `['001']` is valid; `['001\n']`, `[]`,
  duplicates, integers, non-ASCII digits, and short/long strings are invalid
  invocation chapter selections. The unchanged chunks job validator's acceptance
  of the newline case is characterized separately. Only chunks permits chapters.

The 26 maintained jobs, temporary `--config` comparison path, source-font safety,
locale templates, and historical checkpoint semantics are retained. #284 isolates
legacy-only interpretation from composed/lab policy; #286 owns temporary CLI
compatibility. #288 removes maintained complete jobs and dedicated support only
after explicit maintainer comparison acceptance. Shared job schemas/in-memory
validators and historical checkpoint reading remain independently preserved.

## Verification and downstream handoff

`test_component_contract_completion.py` reconciles the field inventory and runs
the S1–S3 validation cases together with job-schema access forbidden.
`test_command_storage_mapping.py` checks the 27 command × route × edition
examples through real preparation APIs, with independent exact location/metadata
expectations. `test_component_selection_mapping.py` covers selection examples,
legacy allowances, preparation retry ordering, and the separate runtime cache.
[Fixture/probe commands](../../tools/gurubodh-cli/tests/fixtures/job-components/README.md)
reproduce standalone, full-suite, and non-editable installed checks. All seven
schema files must match the checkout byte-for-byte in sdist and wheel.

[#298](https://github.com/Team-Gurubodh/gurubodh/issues/298) records verification,
delivery status, and the S4 handoff; [#283](https://github.com/Team-Gurubodh/gurubodh/issues/283)
retains authoritative R01–R39 coverage and whole-issue review. Later runtime work
is not marked implemented by contract evidence: #284 resolution/fallback removal,
#285 auditing, #286 CLI integration, #287 broader discovery/container support,
#288 migration/retirement. #289 process adoption is separate. #284 implementation
waits for #283's completion review, and completion does not authorize merging.
