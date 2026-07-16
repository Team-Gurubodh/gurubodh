# Task-015: Retry Formatting Failed Chapters

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-07-16</date>
<owners>Gurubodh maintainers</owners>
<github_issue>https://github.com/Team-Gurubodh/gurubodh/issues/105</github_issue>
<implementation_github_issue>https://github.com/Team-Gurubodh/gurubodh/issues/123</implementation_github_issue>

## Goal

Add an operator workflow in `gurubodh-utils` that retries Sarvam formatting only
for chapters whose formatting failed after the main content-preparation job
finished.

The workflow must use the durable audit trail and chapter artifacts already
written by R2-backed jobs. It must not rerun DOCX conversion, chapter splitting,
or the full content-preparation job, and it must not depend on any local
generated artifact directory still existing after the original run.

## Context

Task 014 introduced Sarvam formatted Hindi artifacts, chapter-level formatting
metadata, and run audit reports. Repeated testing against the Sarvam API has
shown that formatting calls do fail in normal use. When
`formatting.continue_on_error` is true, the content-preparation job completes
and leaves the affected chapters unformatted.

The current audit trail records enough information to discover and diagnose
these failed chapters:

- chapter metadata includes `formatting.enabled`, `formatting.status`,
  `formatting.warning`, `formatting.source_text_sha256`, formatter token usage,
  and per-call attempt/throttle counts;
- run audit reports summarize formatting outcomes and retry candidates based on
  failed chapter status;
- R2-backed jobs upload raw chapter `.txt` artifacts, chapter metadata JSON,
  and any successful formatted artifacts under the subject artifact prefix.

Task 015 was originally drafted before that audit trail existed. The retry
workflow should now be built around the metadata ledger instead of introducing a
separate retry state file.

The retry workflow also needs a durable cap. Add `formatting.retry_attempts` to
chapter metadata so the command can skip chapters that have already had three
operator retry attempts while preserving `formatting.status: "failed"` and the
latest failure diagnostic.

## Decisions

- Implement retry formatting as a separate command for maintainers.
- Support R2 destinations first.
- Discover candidates from chapter metadata JSON in R2. Run audit reports may
  be used for operator reporting, but chapter metadata is the source of truth
  for retry eligibility.
- Use the canonical raw chapter `.txt` artifact from R2 as the formatter input.
- Store durable retry state in the chapter metadata `formatting` block.
- Add `formatting.retry_attempts` as the cross-run retry counter.
- Treat existing `formatting.attempt_count` as the number of Sarvam request
  attempts made during the most recent formatting operation.
- Treat existing `formatting.retry_count` as the formatter's internal retry
  count within that most recent operation.
- Default retry cap is three operator retry attempts per chapter.
- Skip failed chapters with `formatting.retry_attempts >= 3` by default.
- Continue to record exhausted chapters as failed; do not mark them formatted,
  skipped-unchanged, or successful.
- Upload formatted artifacts only after Sarvam returns valid, validated output.
- Upload updated metadata after each attempted retry so failure state and
  retry-attempt counts remain durable.
- Do not write failure-shaped `*.formatted.json` or `*.formatted.md` artifacts.
- Do not introduce chunking in this implementation. Length-limit failures
  remain failed and count toward `retry_attempts`.

## Target Command Contract

Add a command focused on failed R2-backed formatting:

```bash
gurubodh-utils retry-formatting --config jobs/001_aacharan_shaastra.r2.json
```

Default behavior:

- require `destination.backend: "r2"`;
- list chapter metadata JSON artifacts from the configured R2 subject prefix;
- select chapters where `formatting.enabled` is true,
  `formatting.status == "failed"`, and `formatting.retry_attempts < 3`;
- download each selected chapter metadata JSON and raw chapter `.txt` artifact;
- retry Sarvam formatting using the job's current formatting configuration;
- upload `*.formatted.json`, `*.formatted.md`, and updated metadata when
  formatting succeeds;
- upload updated metadata when formatting fails, without writing display-ready
  formatted artifacts;
- print a final retry summary that separates formatted, failed, skipped, and
  retry-exhausted chapters.

Recommended first flags:

```bash
gurubodh-utils retry-formatting --config jobs/001_aacharan_shaastra.r2.json --dry-run
gurubodh-utils retry-formatting --config jobs/001_aacharan_shaastra.r2.json --chapter 034
gurubodh-utils retry-formatting --config jobs/001_aacharan_shaastra.r2.json --chapters 034,038
gurubodh-utils retry-formatting --config jobs/001_aacharan_shaastra.r2.json --failed-only
```

`--failed-only` should be the default selection mode. A future `--all` or
`--force` flag may be considered later, but the first implementation should
avoid bypassing the retry cap unless a concrete operator need is approved.

Dry-run output should report selected and skipped chapters without making Sarvam
calls and without writing R2 objects:

```text
retry-formatting dry run:
selected=2 skipped=37 retry_exhausted=1
selected chapters:
- 034 formatting.status=failed retry_attempts=0
- 038 formatting.status=failed retry_attempts=2
retry exhausted:
- 041 formatting.status=failed retry_attempts=3
```

Normal execution summary should make it clear whether another retry, chunking,
or manual review is needed:

```text
retry-formatting summary: formatted=1 failed=1 skipped=37 retry_exhausted=1
failed chapters:
- 038 retry_attempts=3 finish_reason=length max_tokens=4096
retry exhausted:
- 041 retry_attempts=3 warning="..."
```

## Metadata Contract

Extend the chapter metadata `formatting` object with:

```json
{
  "retry_attempts": 0
}
```

Semantics:

- `retry_attempts` is an integer with minimum `0`.
- Missing `retry_attempts` in existing metadata should be treated as `0` for
  backward compatibility.
- A retry attempt means the `retry-formatting` command selected the chapter and
  attempted a fresh formatting operation after the original content-preparation
  job.
- The counter should increment once per selected chapter per retry command run,
  regardless of whether Sarvam succeeds, returns invalid output, hits a
  length-limit failure, or raises a retryable request error.
- Do not increment `retry_attempts` during the original chapter-splitting
  formatting pass.
- Do not increment `retry_attempts` for dry-run.
- Do not increment `retry_attempts` when a chapter is skipped before a formatter
  call because formatting is disabled, the chapter is already formatted, the raw
  text artifact is missing, metadata is malformed, or the retry cap has already
  been reached.
- When a retry succeeds, metadata should keep the updated `retry_attempts` value
  and set `formatting.status: "formatted"` with `formatting.warning: null`.
- When a retry fails, metadata should keep `formatting.status: "failed"`, store
  the latest warning, update token usage when available, and persist the updated
  `retry_attempts` value.
- When `retry_attempts >= 3`, default candidate selection should skip the
  chapter but continue reporting it as a failed/retry-exhausted chapter.

The implementation will need to update `chapter_metadata.schema.json`,
metadata generation, tests, and documentation for this new field.

## Defensive Implementation Plan

### R2 Discovery

Use the destination config to derive the chapter artifact prefix:

```text
{destination.prefix}/{destination.subject_dir}/chapters/text_and_metadata/
```

List objects under that prefix and select metadata files:

- include `*.json`;
- exclude `*.formatted.json`;
- ignore non-chapter JSON files defensively.

The storage layer may need a paginated `list_keys` helper for R2. It must handle
more than one page of objects.

### Candidate Selection

For each metadata JSON object:

1. Download and parse metadata.
2. Confirm `formatting.enabled` is true.
3. Confirm the metadata identifies the chapter number and raw text artifact.
4. Normalize missing `formatting.retry_attempts` to `0` in memory.
5. Select the chapter when:
   - `formatting.status` is `failed`;
   - `formatting.retry_attempts < 3`;
   - the chapter matches any explicit `--chapter` or `--chapters` filter.
6. Skip and report the chapter as retry-exhausted when:
   - `formatting.status` is `failed`;
   - `formatting.retry_attempts >= 3`.
7. Skip other chapters when:
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
- validate any existing formatted JSON before treating it as reusable;
- warn when raw text and metadata checksums disagree.

If raw text and metadata disagree, the retry command should continue using the
raw `.txt` as canonical input. On success or failure, updated metadata should
record the checksum for the raw text that was actually retried.

### Formatter Semantics

Reuse the existing Sarvam HTTP formatter path and validation behavior.

The retry command should preserve specific diagnostics for:

- malformed JSON;
- empty content;
- transient HTTP/network failures;
- HTTP 408, 409, 425, 429, 500, 502, 503, and 504;
- missing `SARVAM_API_KEY`;
- unsupported Sarvam client shape;
- `finish_reason='length'` and output-token exhaustion.

Length-limit failures should not be hidden as generic JSON parse failures. They
should remain failed, increment `retry_attempts`, and be visible in command
output and metadata warnings.

### R2 Write Order

On successful formatting:

1. Build `*.formatted.json` and `*.formatted.md`.
2. Validate the formatted JSON artifact shape.
3. Upload `*.formatted.json`.
4. Upload `*.formatted.md`.
5. Update metadata fields for formatted file names, storage references,
   integrity checksums, `formatting.status`, `formatting.warning`,
   `formatting.model_used`, `formatting.source_text_sha256`,
   `formatting.attempt_count`, `formatting.retry_count`,
   `formatting.throttle_sleep_seconds`, `formatting.token_usage`, and
   `formatting.retry_attempts`.
6. Upload metadata JSON last.

On failed formatting:

1. Do not upload display-ready formatted artifacts.
2. Update metadata with `formatting.status: "failed"`, the latest warning,
   `formatting.source_text_sha256`, the latest per-call attempt/throttle fields,
   token usage when available, and the incremented `formatting.retry_attempts`.
3. Preserve existing formatted artifact references only when those artifacts are
   still valid for the current raw text checksum. Otherwise remove stale
   formatted references from metadata.
4. Upload metadata JSON.

Uploading metadata last makes the durable ledger point to formatted artifacts
only after those artifacts have been written.

### Idempotency

The command should be safe to run repeatedly.

- Already formatted chapters with valid formatted artifacts are skipped.
- Failed chapters below the cap are retried by default.
- Failed chapters at or above the cap are reported as retry-exhausted.
- If a previous retry uploaded formatted artifacts but failed before metadata
  upload, the next retry should detect and repair the metadata when possible.
- If `--dry-run` is used, no Sarvam calls and no R2 writes occur.

### Local Storage Boundary

The command may use temporary files as an implementation detail, but it must
work from a clean checkout with only the job config, credentials, and R2 access.

Durable inputs:

- conversion job config;
- R2 chapter metadata JSON;
- R2 raw chapter `.txt`;
- R2 formatted artifacts when present;
- R2 run audit reports for operator visibility.

Durable outputs:

- R2 formatted artifacts for successful retries;
- R2 updated chapter metadata JSON for every attempted retry.

## Risks

- Retrying can increase Sarvam API cost, especially for deterministic
  length-limit failures.
- A retry cap can leave chapters unformatted until chunking or manual review is
  implemented.
- Rewriting metadata in R2 can corrupt the retry ledger if update logic removes
  valid artifact references incorrectly.
- R2 object listing must be paginated; incomplete listing would silently miss
  candidates.
- Concurrent retry runs could race and overwrite metadata. The first version may
  accept this operational risk, but it should be documented.
- Existing metadata without `retry_attempts` must be handled carefully so old
  artifacts remain readable.

## Verification Plan

Unit tests:

- metadata schema accepts `formatting.retry_attempts` and rejects negative
  values;
- metadata generation writes `retry_attempts: 0` for original formatting runs;
- candidate selection includes failed chapters with `retry_attempts < 3`;
- candidate selection reports failed chapters with `retry_attempts >= 3` as
  retry-exhausted;
- missing `retry_attempts` is treated as `0`;
- dry-run performs no Sarvam calls and no R2 uploads;
- successful retry increments `retry_attempts`, uploads formatted JSON,
  formatted Markdown, and metadata in the expected order;
- failed retry increments `retry_attempts`, uploads updated metadata, and does
  not upload display-ready formatted artifacts;
- length-limit responses produce a specific diagnostic and increment
  `retry_attempts`;
- existing valid formatted artifacts can repair metadata after a partial
  previous retry.

Integration-style tests with fake R2:

- Build a fake R2 object map containing metadata and raw text for several
  chapters.
- Include one failed chapter with `retry_attempts: 0`, one failed chapter with
  `retry_attempts: 2`, one failed chapter with `retry_attempts: 3`, one
  formatted chapter, and one disabled chapter.
- Run retry-formatting against the fake R2 client.
- Assert that only the below-cap failed chapters are retried and only the
  expected R2 objects are written.

Manual verification:

```bash
gurubodh-utils retry-formatting \
  --config jobs/001_aacharan_shaastra.r2.json \
  --dry-run
```

Expected: command lists failed chapters below the cap as retry candidates and
failed chapters at three attempts as retry-exhausted.

```bash
gurubodh-utils retry-formatting \
  --config jobs/001_aacharan_shaastra.r2.json \
  --chapter 034
```

Expected: chapter `034` can succeed without rerunning the full job, uploads
formatted artifacts, updates chapter metadata to `formatting.status:
"formatted"`, and records the updated `formatting.retry_attempts`.

```bash
gurubodh-utils retry-formatting \
  --config jobs/001_aacharan_shaastra.r2.json \
  --chapter 038
```

Expected: if the model still hits `finish_reason='length'`, metadata records a
clear length-limit diagnostic, increments `formatting.retry_attempts`, keeps
`formatting.status: "failed"`, and does not upload invalid formatted artifacts.

Regression verification:

```bash
tools/content-preparation/.venv/bin/python -m unittest discover -s tools/content-preparation/tests
```

## Execution Results

Implementation started under issue #123 on 2026-07-16.

## Follow-Up Improvements

- Add chunked formatting for chapters that hit `finish_reason='length'`.
- Add an explicit review/report command that summarizes formatting coverage and
  retry-exhausted chapters across an R2 subject prefix.
- Consider a guarded `--force` flag for maintainers who need to retry chapters
  after the cap is reached.
- Store richer retry history such as `last_attempted_at` and
  `last_error_kind` if a single counter and latest warning are not enough.
- Add concurrency controls or object precondition support if multiple operators
  may retry the same subject at the same time.
