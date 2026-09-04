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
  publication state strings are constrained by enums while their serialized
  values remain unchanged.
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
  service-unavailable recovery, and safe bounded diagnostics. It has no SDK
  dependency.
- `proofreading/validation.py` converts a plain structured-response string into
  typed, validated edits before the provider result crosses the protocol.
- `proofreading/text_comparison.py` owns local word-level comparison.
- `proofreading/artifacts.py` owns canonical chapter output and proofreading
  manifest construction and accepts the narrow `Proofreader` protocol.

Locale selection is an explicit input to the Gemini composition, and the
locale's instruction-template provenance remains an explicit input to canonical
and lab artifact construction. `gurubodh.proofreading` re-exports only the
previously consumed compatibility names; new internal callers should import the
narrow component they use.

## Compatibility rule

Do not add runtime-only keys to schema-shaped job dictionaries. Add a typed
record field instead. When adding another persisted state or artifact record,
validate the JSON payload first and make the conversion to and from the typed
record explicit. Changing a conversion must preserve the corresponding JSON
Schema and artifact semantics unless a separate issue approves a schema change.
