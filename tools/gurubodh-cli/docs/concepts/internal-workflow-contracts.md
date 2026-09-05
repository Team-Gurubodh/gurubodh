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

## Error boundary

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
  configuration record.
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
