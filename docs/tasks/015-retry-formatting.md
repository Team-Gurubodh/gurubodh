# Task-015: Retry Formatting From R2 Artifacts

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-07-14</date>
<owners>Gurubodh maintainers</owners>
<github_issue>https://github.com/Team-Gurubodh/gurubodh/issues/105</github_issue>

## Goal

Define a simple, durable retry workflow for Sarvam Hindi formatting failures in
`gurubodh-utils`.

The retry workflow should allow maintainers to rerun formatting only for
chapters that need it, without rerunning DOCX conversion, chapter splitting, or
the full content-preparation job. It must not rely on local generated artifact
directories. All durable retry state and all required chapter inputs must be
stored in and discovered from Cloudflare R2.

## Context

Task 014 introduced Sarvam formatted Hindi artifacts and issue #103 improved
Sarvam formatter calls by disabling reasoning output and reserving the output
budget with `max_tokens: 4096`.

Live formatting of `jobs/001_aacharan_shaastra.r2.json` still produced two
formatter failures:

```text
warning: formatting failed for chapter 034 CAT004_SUB039_aacharan-shastra_034_v01.01: Sarvam response was not valid JSON: Unterminated string starting at: line 6 column 5 (char 8393)

warning: formatting failed for chapter 038 CAT004_SUB039_aacharan-shastra_038_v01.01: Sarvam response was not valid JSON: Unterminated string starting at: line 5 column 5 (char 86)
```

Investigation showed two different failure modes:

- Chapter 034 succeeded when called again later with the same formatter
  settings. This indicates a transient malformed model response.
- Chapter 038 reproduced as a partial response with `finish_reason='length'`,
  `completion_tokens=4096`, `reasoning_len=0`, and invalid JSON. This indicates
  the formatter hit the configured completion-token limit while still emitting
  JSON.

The installed `sarvamai==0.1.28` SDK accepts `reasoning_effort` and
`max_tokens`, but its `chat.completions` callable does not accept
`response_format`. Therefore the current formatter cannot enforce a JSON schema
through the SDK and must defensively validate, retry, and record failures.

For R2-backed jobs, the main content-preparation run builds artifacts in a
temporary local subject tree and uploads those artifacts to R2. The temporary
tree is not durable and must not be required for later retry. A retry workflow
must treat R2 metadata and chapter text artifacts as the source of truth.

## Decisions

- Add retry formatting as a separate operator workflow, not as an automatic
  rerun of the whole content-preparation job.
- Do not rerun DOCX conversion or chapter splitting during formatting retry.
- Support R2 destinations first. Local destination retry can be considered
  later, but this task is driven by R2 durability requirements.
- Discover retry candidates from chapter metadata JSON files in R2.
- Use the canonical raw chapter `.txt` artifact in R2 as the formatter input.
- Use chapter metadata in R2 as the durable retry ledger.
- Upload formatted artifacts to R2 only after the formatter returns valid,
  validated output.
- Update the chapter metadata JSON in R2 after each retry attempt so the latest
  formatting status, warning, and artifact references are durable.
- Preserve explicitly configured formatting settings from the conversion job.
- Treat malformed JSON responses as retryable when they are not clearly caused
  by the output-token limit.
- Treat `finish_reason='length'` as a clear diagnostic condition. Retrying the
  same full chapter may be allowed by operator request, but the default workflow
  should not hide that the request likely needs chunking or a smaller response.
- Keep `*.formatted.json` and `*.formatted.md` display-ready only. Failure
  state belongs in chapter metadata, not in misleading display artifacts.
- Do not introduce chunking in the first retry-formatting implementation.
  Chunking is a follow-up improvement.

## Target Command Contract

Add a command focused on R2-backed formatting retry:

```bash
gurubodh-utils retry-formatting --config jobs/001_aacharan_shaastra.r2.json
```

Default behavior:

- require `destination.backend: "r2"`;
- list chapter metadata JSON artifacts from the configured R2 destination
  prefix;
- select chapters whose metadata has `formatting.status: "failed"`;
- download each selected chapter's metadata JSON and raw `.txt` artifact;
- retry Sarvam formatting for the raw chapter text;
- upload `*.formatted.json`, `*.formatted.md`, and updated metadata JSON when
  formatting succeeds;
- update metadata JSON with the latest failure warning when formatting fails;
- print a final retry summary.

Recommended first flags:

```bash
gurubodh-utils retry-formatting --config jobs/001_aacharan_shaastra.r2.json --dry-run
gurubodh-utils retry-formatting --config jobs/001_aacharan_shaastra.r2.json --chapter 034
gurubodh-utils retry-formatting --config jobs/001_aacharan_shaastra.r2.json --chapters 034,038
gurubodh-utils retry-formatting --config jobs/001_aacharan_shaastra.r2.json --failed-only
```

`--failed-only` should be the default selection mode. A future `--all` flag may
retry every chapter, but it should not be part of the minimum implementation
unless there is a concrete operator need.

Dry-run output should report what would be retried and why, without making
Sarvam calls and without writing R2 objects:

```text
retry-formatting dry run:
selected=2 skipped=37
selected chapters:
- 034 formatting.status=failed
- 038 formatting.status=failed
```

Normal execution summary should include enough signal to decide whether another
retry, chunking, or manual review is needed:

```text
retry-formatting summary: formatted=1 failed=1 skipped=37
failed chapters:
- 038 finish_reason=length max_tokens=4096
```

## Defensive Implementation Plan

### R2 Discovery

Use the destination config to derive the chapter artifact prefix:

```text
{destination.prefix}/{destination.subject_dir}/chapters/text_and_metadata/
```

List objects under that prefix and select metadata files:

- include `*.json`;
- exclude `*.formatted.json`;
- ignore non-chapter files defensively.

The storage layer may need a paginated `list_keys` helper for R2. The helper
must handle more than one page of objects.

### Candidate Selection

For each metadata JSON object:

1. Download and parse metadata.
2. Confirm `formatting.enabled` is true.
3. Confirm the metadata identifies the chapter number and expected text file.
4. Select the chapter when:
   - `formatting.status` is `failed`; or
   - metadata says `formatted` but expected formatted artifacts are missing; or
   - operator explicitly selected the chapter with `--chapter` or `--chapters`.
5. Skip when:
   - formatting is disabled;
   - formatting status is `formatted` and formatted artifacts exist;
   - formatting status is `skipped-unchanged` and formatted artifacts exist;
   - the chapter does not match the operator's selection flags.

The command should print skip reasons in dry-run mode and concise counts in
normal mode.

### Input Validation

Before calling Sarvam:

- verify the raw chapter `.txt` object exists in R2;
- download the raw chapter text;
- compute `source_text_sha256`;
- compare it with metadata `formatting.source_text_sha256` when present;
- if an existing `*.formatted.json` exists, reuse it only if it is valid,
  `status: "formatted"`, and has the same `source_text_sha256`.

If the raw text checksum differs from the metadata checksum, the retry command
should continue using the raw `.txt` as canonical input and update metadata on
success or failure. It should also include a warning in command output because
the metadata and text were out of sync.

### Formatter Retry Semantics

The formatter should distinguish retryable and non-retryable failures more
precisely than the current generic `SarvamResponseError` behavior.

Retryable by default:

- malformed JSON with `finish_reason` absent or `finish_reason='stop'`;
- empty content without an explicit length-limit diagnostic;
- transient network failures;
- HTTP 408, 409, 425, 429, 500, 502, 503, and 504;
- SDK timeout errors.

Non-retryable by default:

- missing `SARVAM_API_KEY`;
- missing or unsupported Sarvam SDK client shape;
- invalid job config;
- missing raw chapter `.txt` artifact;
- malformed chapter metadata that cannot identify the chapter or text artifact.

Length-limit failures:

- detect `finish_reason='length'` even when partial content exists;
- include `max_tokens`, completion token usage when available, and a clear
  explanation in the warning;
- do not report this as a generic JSON parse error;
- allow the normal retry loop to stop early for this condition unless future
  diagnostics show retrying length failures has value.

### R2 Write Order

On successful formatting:

1. Build `*.formatted.json` in memory or a temporary file.
2. Build `*.formatted.md` in memory or a temporary file.
3. Validate the formatted JSON artifact shape.
4. Upload `*.formatted.json`.
5. Upload `*.formatted.md`.
6. Update metadata fields:
   - `files.formatted_json_filename`;
   - `files.formatted_markdown_filename`;
   - `storage.artifacts.formatted_json`;
   - `storage.artifacts.formatted_markdown`;
   - `integrity.artifacts.formatted_json`;
   - `integrity.artifacts.formatted_markdown`;
   - `formatting.status: "formatted"`;
   - `formatting.warning: null`;
   - `formatting.model_used`;
   - `formatting.source_text_sha256`.
7. Upload the updated metadata JSON last.

Uploading metadata last makes the durable ledger point to formatted artifacts
only after those artifacts have been written.

On failed formatting:

1. Do not upload display-ready formatted artifacts.
2. Update metadata:
   - `formatting.status: "failed"`;
   - `formatting.warning` with the latest diagnostic;
   - `formatting.source_text_sha256`.
3. Preserve existing formatted artifact references only when those artifacts are
   still valid for the current raw text checksum. Otherwise remove stale
   formatted references from metadata.
4. Upload the updated metadata JSON.

### Idempotency

The command should be safe to run repeatedly.

- If a chapter is already formatted and the formatted artifacts are valid for
  the current raw text checksum, skip it.
- If a previous retry uploaded formatted artifacts but failed before metadata
  upload, the next retry should detect and reuse or repair the metadata.
- If a previous retry updated metadata to failed, the next retry should select
  it again by default.
- If `--dry-run` is used, no Sarvam calls and no R2 writes should occur.

### Local Storage Boundary

The command may use temporary files as implementation detail, but must not
require any pre-existing local generated artifact directory. It must work from a
clean checkout with credentials and R2 access.

Durable inputs:

- conversion job config;
- R2 chapter metadata JSON;
- R2 raw chapter `.txt`;
- R2 formatted artifacts when present.

Durable outputs:

- R2 formatted artifacts;
- R2 updated chapter metadata JSON.

## Risks

- Sarvam may continue returning malformed JSON because current SDK calls cannot
  enforce `response_format`.
- Retrying can increase API cost, especially if repeated against length-limit
  failures.
- Rewriting metadata in R2 can corrupt the retry ledger if the update logic
  removes valid artifact references incorrectly.
- R2 object listing must be paginated; incomplete listing would silently miss
  retry candidates.
- Concurrent retry runs could race and overwrite metadata. The first version may
  accept this operational risk, but it should be documented.
- `sarvam-105b` fallback may time out or have different latency/cost behavior.
- Length-limit failures are unlikely to be fixed by simple retry and may
  require chunking or a different response contract.
- If raw chapter text and metadata disagree, retry may repair formatting while
  exposing a deeper artifact consistency issue.

## Verification Plan

Unit tests:

- R2 key discovery selects metadata JSON files and excludes
  `*.formatted.json`.
- Candidate selection includes `formatting.status: "failed"`.
- Candidate selection skips formatted chapters with valid formatted artifacts.
- Candidate selection includes formatted chapters whose formatted artifacts are
  missing.
- Dry-run performs no Sarvam calls and no R2 uploads.
- Successful retry uploads formatted JSON, formatted Markdown, and metadata in
  the expected order.
- Failed retry uploads updated metadata but no display-ready formatted
  artifacts.
- Length-limit responses produce a specific diagnostic rather than a generic
  invalid JSON warning.
- Malformed JSON with `finish_reason='stop'` is retryable.
- Existing valid formatted artifacts can repair metadata after a partial
  previous retry.

Integration-style tests with fake R2:

- Build a fake R2 object map containing metadata and raw text for several
  chapters.
- Mark one chapter failed, one formatted, one disabled, and one formatted with
  missing artifacts.
- Run retry-formatting against the fake R2 client.
- Assert that only the correct chapters are retried and only the expected R2
  objects are written.

Manual verification:

```bash
gurubodh-utils retry-formatting \
  --config jobs/001_aacharan_shaastra.r2.json \
  --dry-run
```

Expected: command lists chapters `034` and `038` as retry candidates when their
metadata remains failed.

```bash
gurubodh-utils retry-formatting \
  --config jobs/001_aacharan_shaastra.r2.json \
  --chapter 034
```

Expected: chapter `034` can succeed without rerunning the full job, uploads
formatted artifacts, and updates chapter metadata to `formatting.status:
"formatted"`.

```bash
gurubodh-utils retry-formatting \
  --config jobs/001_aacharan_shaastra.r2.json \
  --chapter 038
```

Expected: if the model still hits `finish_reason='length'`, metadata records a
clear length-limit diagnostic and the command does not upload invalid formatted
artifacts.

Regression verification:

```bash
tools/content-preparation/.venv/bin/python -m unittest discover -s tools/content-preparation/tests
```

## Execution Results

No implementation has been started for this task.

This task records the proposed design for a future issue. The implementation
should create a new GitHub issue or use an existing issue that explicitly
approves the coding scope before changing source files.

## Follow-Up Improvements

- Add chunked formatting for chapters that hit `finish_reason='length'`.
- Store chunk-level provenance in formatted JSON so reviewers can understand how
  a formatted artifact was assembled.
- Add a configurable maximum retry-attempt count per chapter in metadata to
  avoid endless retries of deterministic failures.
- Add `last_attempted_at`, `attempt_count`, and `last_error_kind` to formatting
  metadata if operational retry history becomes important.
- Add optional fallback-model behavior for selected retryable failures, with
  clear cost and timeout controls.
- Explore Sarvam tool-calling as a structured-output substitute while the SDK
  lacks `response_format`.
- Revisit SDK support periodically. If Sarvam adds official `response_format`
  or structured-output support, update the formatter to use it and simplify
  retry handling.
- Add a review/report command that summarizes formatting coverage across an R2
  subject prefix without making Sarvam calls.
- Add concurrency controls or object precondition support if multiple operators
  may retry the same subject at the same time.
- Add a command to retry only length-limit failures once chunking is available.
