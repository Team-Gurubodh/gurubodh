# Internal workflow contracts

The Gurubodh CLI keeps its JSON Schemas as the authority for persisted jobs and
artifacts. Inside the application, the highest-risk cross-module values use the
typed records in `gurubodh/contracts.py`; they are not new serialized formats.

## Conversion boundaries

- Job loaders validate a raw JSON object, copy it, and return `PrepSubjectJob`,
  `GenerateChunksJob`, or `GenerateDocxJob`. Locale, proofreading settings,
  compiled chapter patterns, and semantic-chunk settings live on those records.
  `PreparedJob.to_payload()` returns only the original JSON-compatible job.
- Candidate manifest JSON is validated and converted to
  `CandidateManifestBinding` and `CandidateChapterBinding`. Validated chapter
  metadata and text become `MaterializedChapterSource` records. Readiness
  manifests receive only `serialized_binding()` or explicit payload conversions.
- A successful chapter proofread returns `ProofreadingOutcome` plus immutable
  `CheckpointArtifactRecord` values. `proofreading_payload()` produces the
  existing checkpoint/manifest representation without consuming the outcome.
- Prep job-state JSON enters and leaves the runtime through
  `PrepCheckpointState.from_payload()` and `to_payload()`. Prep, chapter, and
  publication state strings are constrained by enums, and the typed
  `replacement_authorized` property exposes the required schema-version-2 job
  intent without consulting invocation flags.
- Chunk and DOCX workflows use typed generation summaries internally. Their
  `to_payload()` methods provide the existing dictionaries used by artifact and
  audit writers.

Payload conversion methods return isolated copies. Mutating a serialization
payload therefore cannot reset or consume the typed workflow result that owns
it.

`job_components.ComponentCatalog` loads and validates fixed component IDs from
an explicit CLI root. `job_composition.resolve_job` constructs a fresh mapping
field by field and calls the same preparation APIs. Its `ResolvedJob` separates
the typed prepared job from `JobResolutionInputs`: frozen component byte
snapshots, invocation/profile selections, and used root bindings. These snapshots
are captured at resolution time and never reread to describe an assembled run.
They are internal contracts for #285; no audit/checkpoint schema changes are
introduced. The [configuration reference](../reference/job-configurations.md#compose-through-the-python-api)
documents selection, routing, environment resolution, and remaining series work.

## Error boundary

`validate_component(instance, component_name, path=None, *, expected_id=None)`
validates all seven registered component kinds in memory. The additional S3
contracts are recorded in [#296](https://github.com/Team-Gurubodh/gurubodh/issues/296).
The [S4 field mapping](https://github.com/Team-Gurubodh/gurubodh/issues/298#issuecomment-5571636607)
reconciles component ownership with the existing preparation APIs. Validation returns
`None` without mutation, component lookup, or policy construction. `path` supplies
diagnostic context; `expected_id` checks resource identity. Unknown kinds and
malformed components raise `ConfigurationError`. Each job/component/artifact
entry point selects its error domain explicitly.

Job component schemas own their full specifications without external property
references. S2 uses only in-document definitions for shared manifest shapes.
The cached validator loads only the requested schema, with no job definition
schema or remote retrieval. After structural validation, it rejects proofreading
progress intervals above the timeout and compiles manifest regex patterns with
explicit flags to reject invalid Python syntax. Compiler errors are sanitized;
compiled values are discarded. Expected identity uses `profile_id`, `manifest_id`,
or `locale` for S1/S2 kinds; S3 identity fields are specified in #296. See
[Decision-0009](https://github.com/Team-Gurubodh/gurubodh/issues/292#issuecomment-5571635810)
for the profile contract and
[Decision-0010](https://github.com/Team-Gurubodh/gurubodh/issues/294#issuecomment-5571636132)
for subject/locale fields and the boundary with later composition work.

Expected failures below `gurubodh.cli` use the small hierarchy in
`gurubodh/errors.py`: configuration, source validation, storage/publication,
and processing failures. The CLI catches the common `GurubodhError` base and
translates it to the existing `argparse` error exit at the command boundary.
Reusable modules do not raise `SystemExit`.

`R2Downloader`, `R2Uploader`, `R2Client`, and `Proofreader` protocols document
the injectable storage and provider seams. Production clients and test fakes
satisfy those protocols without inheriting a framework base class or being cast
to `Any`.

## Prep-subject boundaries

The resumable prep workflow is composed from explicit collaborators while its
persisted job, chapter, proofreading, publication, and manifest schemas remain
unchanged:

- `canonical_release.py` owns the persisted release-state constants and the
  release readiness gate used by derived commands. It is foundational and does
  not import prep orchestration.
- `prep_checkpoint_store.py` defines the checkpoint persistence protocol and
  its local and R2 implementations. Both stores load typed state, commit state
  atomically, commit checkpoint artifacts before state, restore and remove a
  workspace, and archive prior state.
- `prep_coordination.py` owns the local advisory lock and R2 advisory lease
  transitions. It does not process chapters or publish artifacts, and the R2
  lease remains only a guardrail.
- `prep_publication.py` owns local and R2 canonical promotion plus the
  separately invoked overwrite cleanup operations. The canonical content
  manifest remains the last promoted or uploaded artifact.
- `prep_checkpoint.py` owns backend-neutral checkpoint and chapter state
  transitions and presents a session facade over those ports.
- `prep_subject_checkpoints.py` is the application orchestrator and retained
  compatibility entry point for the two prep pipelines. It coordinates source
  preparation, proofreading, checkpoint transitions, publication, and audit
  outcomes without implementing a storage backend.

The collaborators accept the existing `R2Client` and `Proofreader` protocols,
along with injected clock, sleeper, progress, and filesystem-backed roots used
by focused tests. Prep resumability remains distinct from the non-resumable
derived-artifact lifecycle; both reuse the lower-level storage client and
upload primitive where their semantics match.

Checkpoint schema version 2 persists replacement authorization when a new job
starts. Compatible resume restores that job-level value for canonical
replacement and post-publication invalidation. Legacy incomplete version-1
states are ambiguous and require restart with `--overwrite`; succeeded
version-1 states migrate with authorization set to false and remain usable by
derived-release gates.

## Proofreading boundaries

Proofreading is a package of independently testable components rather than a
single provider-specific workflow module:

- `proofreading/settings.py` owns the explicit provider and request-policy
  configuration record. Every policy argument is required. Lab loads its complete
  JSON-selected policy through `resolve_lab_proofreading()` before creating output.
- `proofreading/gemini.py` is the only Gemini SDK adapter. It owns client
  initialization, request construction, and bounded in-flight progress.
- `proofreading/service.py` applies provider-neutral orchestration around a raw
  transport and returns the shared `ProofreadingProviderResponse` contract.
- `proofreading/policy.py` owns pacing, retry classification and delay,
  and service-unavailable recovery. It has no SDK dependency.
- `proofreading/validation.py` converts a plain structured-response string into
  typed, validated edits before the provider result crosses the protocol.
- `proofreading/text_comparison.py` owns local word-level comparison.
- `proofreading/artifacts.py` owns canonical chapter output and proofreading
  manifest construction and accepts the narrow `Proofreader` protocol.

`gurubodh/diagnostics.py` is the shared leaf owner for bounded request-diagnostic
sanitization used by auditing and proofreading. It depends on no proofreading,
retry-policy, provider, audit, or orchestration component. The former
`proofreading.policy.safe_request_diagnostics` import remains a compatibility
alias to the same implementation; production consumers import the shared owner
directly.

Locale selection is an explicit input to the Gemini composition, and the
locale's instruction-template provenance remains an explicit input to canonical
and lab artifact construction. `gurubodh.proofreading` re-exports only the
previously consumed compatibility names; new internal callers should import the
narrow component they use.

## Import ownership and verification

`gurubodh.ml.errors` owns the shared `ModelCacheConfigError` leaf exception.
Embedding infrastructure and semantic-chunking configuration consume that same
class; `gurubodh.ml.semantic_chunking.config.ModelCacheConfigError` remains a
compatible import and catch target. Embedding infrastructure must not depend on
semantic-chunking modules.

`SemanticChunkConfig` requires every policy argument, including nullable device
and model revision. `from_env()` binds only the existing model-cache input;
missing policies fail. `SemanticChunker` requires an explicit configuration and
rejects `None`. The model cache remains a runtime environment input with no
guessed location.

`gurubodh.ml.semantic_chunking` eagerly exports only `SemanticChunkConfig`,
`Chunk`, and `ChunkedDocument`. The supported `SemanticChunker`,
`ParagraphSegmenter`, and `SemanticChunkingParagraphSegmenter` package imports
resolve lazily to their original classes. Importing the package, configuration,
or models alone must not load chunker, segmenter, or embedding implementation.
New internal callers should import the narrow component they consume.

Dependency direction runs from CLI and command orchestration to reusable
components. Only `gurubodh.__main__`, the module entry point, imports the main
`gurubodh.cli` module; the installed console script also targets `cli:main`.
Reusable modules must not import lab commands, `pipelines`,
`prep_subject_checkpoints`, or the tokenization command adapter. In particular,
canonical source/release validation stays independent of prep orchestration.
Importing `contracts` alone must not load other Gurubodh components, including
proofreading services or provider adapters.

`tests/test_import_boundaries.py` replaces the former canonical/prep string
guard with focused declared-import checks and a fresh interpreter for **each**
discovered package module. Imports may not load provider/model SDKs, perform
network or process operations, or invoke CLI/workflow entry functions. The
checks distinguish eager imports, `TYPE_CHECKING` references, deferred function
imports, and deliberate `__getattr__` compatibility exports. Fresh-process
guards additionally cover implicit parent-package initialization and transitive
runtime dependencies, which a direct-import scan cannot establish. A static
graph cycle involving type references or lazy exports is not by itself a
runtime defect; raw pydeps cycle counts are not a pass/fail criterion.

From `tools/gurubodh-cli`, run the focused checks or normal verification:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p test_import_boundaries.py -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p test_semantic_chunking.py -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p test_job_composition.py -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -v
```

The existing `gurubodh-cli container` pull-request workflow runs full unittest
discovery, including these import guards and deterministic fake-model chunking
checks. Container runtime smoke checks are described in the
[R2 runbook](../operations/r2-production-runs.md#build-and-inspect-locally).

## Compatibility rule

Do not add runtime-only keys to schema-shaped job dictionaries. Add a typed
record field instead. When adding another persisted state or artifact record,
validate the JSON payload first and make the conversion to and from the typed
record explicit. Changing a conversion must preserve the corresponding JSON
Schema and artifact semantics unless a separate issue approves a schema change.

## Component contract verification

The [component fixtures](../../tests/fixtures/job-components/) are independent
test inputs. The [field inventory](../../tests/fixtures/job-components/assembled-job-field-mapping.json)
records every assembled job field, owner, and presence rule; the completeness
test compares it against job schemas. Maintain this fixture independently
when an accepted contract changes; do not generate expectations from schemas.

### S1 profiles

These independent fixtures are not a production catalog.
`proofreading/gemini-3.6-flash-v1.json` declares the accepted Gemini policy;
`chunking/bge-m3-v1.json` preserves the maintained BGE-M3 settings.

`tests/test_profile_contracts.py` mutates one property per invalid case, with
expectations independent of the schemas. Cases cover every envelope/setting
deletion, unknown root/nested fields, wrong kinds/versions, unsafe or unversioned
IDs, invalid objects/types/constants/bounds, and timeout/interval conflicts.
Tests also cover nullable devices, false booleans, non-mutation, resource-ID
matching, local property ownership, missing schemas, deterministic diagnostics,
and maintained-job compatibility. Each schema runs through plain Draft 2020-12
validation and the shared validator with job definition schema access forbidden.

### S2 subjects and locales

`subjects/aps-hindi.json` declares APS/Hindi with literal splitting and no
profile overrides. `subjects/unicode-bilingual.json` declares Unicode/Hindi
with regex splitting and Unicode/Marathi with disabled splitting, independent
releases, and manifest/edition profile selections. `locales/hi-IN.json` and
`locales/mr-IN.json` declare the metadata and markers specified for #284.
All are test fixtures, not maintained catalog entries.

`tests/test_subject_locale_contracts.py` independently enumerates required fields
and mutates fixtures for invalid types, versions, identities, paths, encodings,
locale declarations, split shapes, flags, and profile references. Structural
rejections run through standalone Draft 2020-12 and the shared validator;
Python regex syntax is a separate semantic check. Tests assert non-mutation,
safe diagnostics, local property ownership, and forbidden job-schema access.
Mapping tests separately use real preparation functions for all three commands,
including prep local/R2 source shapes, without executing sources or providers.

From the CLI root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p test_profile_contracts.py -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p test_subject_locale_contracts.py -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p test_schema_validation.py -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -v
```

### S3 and S4 combined verification

S3 fixtures add four command branches, development stores, and all three storage
profiles. Their authoritative contract is [#296](https://github.com/Team-Gurubodh/gurubodh/issues/296).
S4 reuses the S1–S3 validation cases in `component_contract_cases.py` under one
job-schema access prohibition, including standalone structural failures for all
profile cases. Semantic interval/regex checks remain distinct from JSON Schema.
The combined ownership check compares raw schema documents to cached validators
and rejects external property references/default annotations. Separate mapping
tests cover the documented field inventory, the existing 27-case matrix, twelve
whole-profile selection examples, applicability, legacy complete-job shapes,
preparation retry ordering, and the separate runtime model cache.
Selection examples are contract oracles for #284, not a production resolver.

Focused checkout checks (run the full CLI suite above as well):

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p 'test_component*.py' -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p 'test_command_storage*.py' -v
```

### Distribution verification

Build in a temporary copy to keep build metadata out of the checkout. The default
`build` command creates an sdist, then its wheel, testing both distributions.
Install only schema-validation dependencies; invoke no models or providers.
Run these commands from the CLI root using Python 3.12:

```bash
PROFILE_CHECK_ROOT=$(mktemp -d)
mkdir "$PROFILE_CHECK_ROOT/source"
cp -R gurubodh config pyproject.toml README.md "$PROFILE_CHECK_ROOT/source/"
cp -R tests/fixtures/job-components "$PROFILE_CHECK_ROOT/fixtures"
cp tests/check_installed_components.py tests/check_component_distributions.py tests/component_contract_cases.py tests/test_component_contract_completion.py tests/test_profile_contracts.py tests/test_subject_locale_contracts.py tests/test_command_storage_contracts.py "$PROFILE_CHECK_ROOT/"
.venv/bin/python -m venv "$PROFILE_CHECK_ROOT/venv"
"$PROFILE_CHECK_ROOT/venv/bin/python" -m pip install build 'setuptools>=68' wheel 'jsonschema>=4.23,<5' 'referencing>=0.35,<1'
"$PROFILE_CHECK_ROOT/venv/bin/python" -m build --no-isolation --outdir "$PROFILE_CHECK_ROOT/dist" "$PROFILE_CHECK_ROOT/source"
"$PROFILE_CHECK_ROOT/venv/bin/python" -B tests/check_component_distributions.py config/job-components/schemas "$PROFILE_CHECK_ROOT"/dist/*.tar.gz "$PROFILE_CHECK_ROOT"/dist/*.whl
"$PROFILE_CHECK_ROOT/venv/bin/python" -m pip install --no-deps "$PROFILE_CHECK_ROOT"/dist/*.whl
cd "$PROFILE_CHECK_ROOT"
"$PROFILE_CHECK_ROOT/venv/bin/python" -I -B check_installed_components.py fixtures
```

The probe runs the all-seven ownership check and 44 reused validation methods
with job schemas present, then repeats with them physically absent. Imports and
schema locations must originate in the installation outside the checkout; all
validation runs block networking. Job/artifact domain checks occur separately
before hiding job schemas. No mapping case runs with job schemas absent.
The distribution checker compares every component schema byte-for-byte against
the checkout in both the sdist and its wheel. The full CLI suite separately
includes all 26 maintained jobs, preparation, fonts, checkpoints, and imports.

The earlier S1/S2/S3 probes remain available as `check_installed_profiles.py`,
`check_installed_subject_locales.py`, and `check_installed_command_storage.py`.
The combined probe covers their component-validation scope; broader catalog
and container discovery belong to #287.
