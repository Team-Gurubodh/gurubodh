# Task-014: Sarvam Paragraph Segmentation Metadata

<record_type>task_plan</record_type>
<status>proposed</status>
<owners>Gurubodh maintainers</owners>
<github_issue>https://github.com/Team-Gurubodh/gurubodh/issues/126</github_issue>
<source_start_tag>task-013-complete-before-formatting</source_start_tag>
<supersedes_approach>full-text Sarvam formatted artifacts</supersedes_approach>

## Goal

Implement an economical Sarvam-backed paragraph segmentation workflow for
`gurubodh-utils`.

The goal is only to divide canonical raw Hindi chapter text into readable
paragraphs. Sarvam must not return rewritten chapter text, formatted chapter
text, summaries, translations, titles, tags, or any other derived prose.

Instead, Sarvam should return a compact paragraph span map: character index
ranges into the original raw chapter text. The content-preparation metadata can
store those spans, and downstream readers can render display paragraphs on
demand by slicing the canonical raw chapter `.txt` artifact.

This task should begin from git tag:

```text
task-013-complete-before-formatting
```

It intentionally drops the full-text formatted artifact model added between
`task-013-complete-before-formatting` and
`task-015-retry-formatting-complete`, while carrying forward the useful
infrastructure and lessons learned from that work.

## Core Requirement

For each chapter, when paragraph segmentation is enabled:

1. Write the canonical raw chapter `.txt` artifact exactly as before.
2. Send that exact raw text to Sarvam.
3. Ask Sarvam to return only paragraph character spans.
4. Validate the returned spans against the exact raw text.
5. Store the validated span map inside the chapter metadata JSON.
6. Do not write separate `*.formatted.json` or `*.formatted.md` files.
7. Do not store Sarvam-returned document text anywhere.
8. Continue the content-preparation job when segmentation fails and
   `continue_on_error` is true.
9. Record segmentation failures, request attempts, throttling, token usage, and
   retry eligibility in metadata and run audit reports.

## Why This Approach

The previous full-text formatting approach asked Sarvam to return a near-full
copy of the chapter text as JSON. That consumed large completion-token budgets
and could hit Sarvam output limits.

This new approach asks Sarvam only for paragraph boundaries. For a chapter with
thousands of Hindi characters, the response should usually be a small JSON array
of integer pairs. The expected completion-token cost should be much lower than
returning the full formatted chapter text.

The canonical source text remains unchanged and authoritative. Paragraph display
becomes a metadata-driven rendering concern.

## Explicit Non-Goals

- Do not generate or store `*.formatted.json`.
- Do not generate or store `*.formatted.md`.
- Do not store rewritten, corrected, punctuated, translated, or summarized text.
- Do not use Sarvam to generate chapter titles.
- Do not use Sarvam to generate summaries, tags, descriptors, embeddings, or RAG
  chunks.
- Do not ingest paragraph segmentation output into Strapi in this task.
- Do not introduce a standalone R2 batch processor.
- Do not implement chunking unless a later issue proves it is still needed.
- Do not carry over formatted artifact storage references, formatted artifact
  checksums, or formatted artifact reuse logic.

## Prompt Direction

The system prompt should be focused on paragraph segmentation and output-token
economy.

Recommended starting prompt:

```text
You are an expert Hindi paragraph segmenter.

Given raw Hindi text, return ONLY a minified JSON array of paragraph character spans.

Rules:
1. Group sentences into paragraphs based on shared theme, idea, or logical flow.
2. Do not create one-or-two-sentence paragraphs unless clearly needed.
3. Do not translate, summarize, rewrite, omit, or return any document text.
4. Use zero-based character indices into the original input text.
5. Each span must be [start_char_index,end_char_index].
6. Return only valid minified JSON. No markdown, no explanation.
```

The final implementation should rely on Sarvam structured output rather than
prompt-only JSON enforcement.

## Span Semantics

Span semantics must be precise and stable.

- Indices are zero-based.
- Indices are Python string indices into the exact UTF-8-decoded raw chapter
  text value used by `gurubodh-utils`.
- End indices are exclusive.
- Each span is `[start, end)`.
- Rendering uses `chapter_text[start:end]`.
- Spans must be ordered by ascending `start`.
- Spans must not overlap.
- Each span must satisfy `0 <= start < end <= len(chapter_text)`.
- The full set of spans may either:
  - cover the full text after trimming paragraph-boundary whitespace; or
  - cover only non-empty paragraph regions while allowing whitespace gaps.

The chosen coverage rule must be documented and tested. The recommended first
implementation is to allow whitespace-only gaps between spans, while rejecting
gaps that contain non-whitespace text.

## Structured Response Schema

Prefer Sarvam `response_format` with `type: "json_schema"` and strict mode.

If Sarvam reliably supports a root array schema, the target response can be a
minified root array:

```json
[[0,123],[123,286],[286,421]]
```

Corrected root-array schema:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "gurubodh_paragraph_spans",
    "strict": true,
    "schema": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "array",
        "prefixItems": [
          {
            "type": "integer",
            "minimum": 0
          },
          {
            "type": "integer",
            "minimum": 0
          }
        ],
        "minItems": 2,
        "maxItems": 2,
        "additionalItems": false
      }
    }
  }
}
```

If root arrays are unreliable with Sarvam structured output, use an object
wrapper:

```json
{"paragraph_spans":[[0,123],[123,286],[286,421]]}
```

Object-wrapper schema:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "gurubodh_paragraph_span_response",
    "strict": true,
    "schema": {
      "type": "object",
      "additionalProperties": false,
      "required": ["paragraph_spans"],
      "properties": {
        "paragraph_spans": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "array",
            "prefixItems": [
              {
                "type": "integer",
                "minimum": 0
              },
              {
                "type": "integer",
                "minimum": 0
              }
            ],
            "minItems": 2,
            "maxItems": 2,
            "additionalItems": false
          }
        }
      }
    }
  }
}
```

The object-wrapper response costs a few more output tokens but may be more
portable across structured-output implementations.

## Configuration Contract

Do not reuse the old `formatting` name unless maintainers explicitly prefer it.
This capability is paragraph segmentation, not formatted text generation.

Recommended conversion job config block:

```json
{
  "paragraph_segmentation": {
    "enabled": true,
    "provider": "sarvam",
    "model": "sarvam-105b",
    "fallback_model": "sarvam-105b",
    "output_shape": "root-array",
    "continue_on_error": true,
    "delay_seconds": 4,
    "max_retries": 1,
    "regenerate": "when-source-checksum-changes",
    "reasoning_effort": null,
    "max_tokens": 1024
  }
}
```

Recommended defaults:

```json
{
  "enabled": false,
  "provider": "sarvam",
  "model": "sarvam-105b",
  "fallback_model": "sarvam-105b",
  "output_shape": "root-array",
  "continue_on_error": true,
  "delay_seconds": 4,
  "max_retries": 1,
  "regenerate": "when-source-checksum-changes",
  "reasoning_effort": null,
  "max_tokens": 1024
}
```

Notes:

- `max_tokens` should be much lower than the previous `4096` default because
  the output is only a span map.
- Keep `max_tokens` configurable so real runs can tune it.
- If `root-array` fails in live testing, switch default `output_shape` to
  `object-wrapper`.
- Keep `fallback_model` in the contract even if the first implementation does
  not actively use fallback escalation.

## Chapter Metadata Contract

Store paragraph segmentation directly in the existing chapter metadata JSON.

Recommended metadata shape:

```json
{
  "paragraph_segmentation": {
    "enabled": true,
    "provider": "sarvam",
    "model": "sarvam-105b",
    "fallback_model": "sarvam-105b",
    "model_used": "sarvam-105b",
    "status": "segmented",
    "warning": null,
    "source_text_sha256": "...",
    "index_unit": "python-codepoint",
    "span_semantics": "zero-based-end-exclusive",
    "spans": [[0, 123], [123, 286], [286, 421]],
    "attempt_count": 1,
    "retry_count": 0,
    "retry_attempts": 0,
    "throttle_sleep_seconds": 0,
    "token_usage": {
      "completion_tokens": 83,
      "prompt_tokens": 2100,
      "total_tokens": 2183
    }
  }
}
```

Allowed statuses:

- `disabled`
- `segmented`
- `skipped-unchanged`
- `failed`

Field semantics:

- `source_text_sha256` is the SHA-256 of the exact raw chapter text string used
  to produce the spans.
- `spans` is present only when status is `segmented` or `skipped-unchanged`.
- `warning` is non-null when status is `failed`.
- `attempt_count` is Sarvam request attempts during the most recent operation.
- `retry_count` is internal formatter retry count during the most recent
  operation.
- `retry_attempts` is the cross-run operator retry counter used by the retry
  command.
- `token_usage` records Sarvam response usage when available.

## On-Demand Paragraph Rendering

Downstream rendering should:

1. Load canonical raw chapter text.
2. Load chapter metadata.
3. Verify `paragraph_segmentation.status` is `segmented` or
   `skipped-unchanged`.
4. Verify `paragraph_segmentation.source_text_sha256` matches the raw text.
5. Validate spans defensively.
6. Render paragraphs with `text[start:end].strip()`.
7. Join paragraphs with blank lines for display when Markdown-style output is
   needed.

If checksum or span validation fails, rendering must fall back to raw text or
return a clear invalid-segmentation error. It must not silently slice corrupted
or stale spans.

## Carry Forward From Previous Work

Carry these implementation choices from the work between
`task-013-complete-before-formatting` and
`task-015-retry-formatting-complete`.

### Direct Sarvam HTTP Caller

Use direct HTTP for Sarvam chat completions.

Carry forward:

- `POST https://api.sarvam.ai/v1/chat/completions`
- `api-subscription-key` from `SARVAM_API_KEY`
- explicit JSON request body
- `reasoning_effort: null`
- configurable `max_tokens`
- `response_format`
- HTTP retryable/permanent error classification
- no secrets in logs, reports, fixtures, or docs

Reason:

The previous implementation proved that the installed Sarvam SDK path did not
forward `response_format` reliably enough for this workflow.

### Structured JSON Output

Use Sarvam structured output through `response_format`.

Reason:

The paragraph span response is compact but must be mechanically valid. Strict
structured output reduces parser ambiguity and avoids prompt-only JSON repair.

### Progress Reporting

Carry forward the small progress reporter pattern.

Progress should report:

- chapter index and total;
- segmentation start;
- model and character count;
- Sarvam attempt number;
- retry sleep;
- skipped unchanged;
- segmentation success and span count;
- segmentation failure;
- R2 download/upload/listing milestones;
- retry command discovery and per-chapter processing.

Do not print raw chapter text, request bodies, API keys, or secrets.

### Throttle And Retry Policy

Carry forward:

- steady delay before every Sarvam request after the first request in a run;
- default `delay_seconds: 4`;
- default `max_retries: 1`;
- hard cap at one retry after the initial call;
- no retries for permanent failures such as missing credentials or invalid
  response schema.

Reason:

Even small responses still consume API requests and can hit provider limits.

### Continue-On-Error Semantics

Carry forward `continue_on_error`.

When enabled:

- a failed Sarvam segmentation call must not fail canonical chapter generation;
- metadata should record status `failed` and warning details;
- audit reports should list failed chapters and retry candidates.

When disabled:

- segmentation failure may fail the job with a clear error.

### Source Text Checksum

Carry forward source text checksum behavior.

Reason:

Span maps are valid only for the exact text used to generate them. Every span
map must be tied to a `source_text_sha256`.

### Run Audit Reports

Carry forward run audit reports.

Reports should summarize:

- run identity;
- job identity;
- configuration snapshot;
- chapter count;
- paragraph segmentation summary counts;
- per-chapter segmentation status;
- warnings;
- retry candidates;
- retry-exhausted chapters;
- throttle evidence;
- Sarvam token usage totals.

Reports must exclude secrets, request bodies, and full chapter text.

### Token Usage Recording

Carry forward token usage recording in both metadata and audit reports.

Reason:

This implementation is justified by output-token economy. The audit trail should
make that measurable across real jobs.

### R2 Retry Workflow Pattern

Carry forward the retry-command pattern, redesigned for segmentation.

Recommended command:

```bash
gurubodh-utils retry-paragraph-segmentation --config jobs/001_aacharan_shaastra.r2.json
```

The command should:

- require R2 destination in the first implementation;
- discover chapter metadata JSON objects from R2;
- select failed segmentation chapters below the retry cap;
- download canonical raw `.txt`;
- retry Sarvam segmentation;
- upload updated metadata;
- not write formatted artifacts;
- support `--dry-run`, `--chapter`, and `--chapters`;
- report retry-exhausted chapters.

## Drop From Previous Work

Do not carry over:

- `*.formatted.json` generation;
- `*.formatted.md` generation;
- formatted artifact storage references;
- formatted artifact integrity checksums;
- formatted artifact reuse logic;
- prompt instructions asking Sarvam to return paragraphs of text;
- local or R2 logic that treats display-ready formatted text as a durable
  artifact.

## Stage 1: Task Brief And Issue Plan

### Goal

Add this approved task brief to `docs/tasks/` after the repository is prepared.

### Scope

- Add a task record describing paragraph segmentation metadata.
- Document the goal, non-goals, schema shape, metadata shape, prompt direction,
  carry-forward decisions, dropped old behavior, implementation stages, risks,
  and verification plan.

### Acceptance Criteria

- Task brief exists under `docs/tasks/`.
- It references the start tag `task-013-complete-before-formatting`.
- It clearly states that the new approach does not generate formatted text
  artifacts.
- It breaks implementation into focused stages that can become GitHub issues.

### Verification

- Review Markdown for consistency with existing `docs/tasks/` style.

## Stage 2: Configuration And Schema Contract

### Goal

Add the optional `paragraph_segmentation` conversion job config block.

### Scope

- Bump conversion job schema version.
- Add `paragraph_segmentation` to `conversion_job.schema.json`.
- Add config constants and validation/defaulting.
- Preserve disabled-by-default behavior when omitted.
- Add migration support from the previous schema version.
- Preserve existing jobs by adding explicit disabled defaults during migration.
- Update docs and schema index.

### Acceptance Criteria

- Omitted `paragraph_segmentation` means disabled.
- Explicit disabled config validates.
- Enabled Sarvam config validates.
- Invalid providers, models, output shapes, retry values, regeneration modes,
  and `max_tokens` values are rejected.
- Migration dry-run previews the disabled defaults.
- Migration apply writes the schema bump and disabled defaults.
- Unsupported schema versions are refused.
- Existing non-segmentation jobs behave unchanged.

### Verification

- Focused config and migration tests.
- Full content-preparation test suite if available.

## Stage 3: Sarvam Paragraph Segmenter Module

### Goal

Implement the Sarvam paragraph segmentation client without integrating it into
chapter splitting yet.

### Scope

- Add a module such as `gurubodh_utils/paragraph_segmentation.py`.
- Implement direct HTTP chat-completion caller or reuse a shared Sarvam HTTP
  helper if one exists.
- Read `SARVAM_API_KEY` from the environment.
- Send structured `response_format`.
- Send `reasoning_effort` and `max_tokens` from normalized config.
- Apply retry and throttling policy.
- Parse Sarvam response content.
- Detect `finish_reason: "length"` and raise a clear output-token diagnostic.
- Record token usage.
- Validate returned spans against the exact input text.

### Acceptance Criteria

- Module imports without Sarvam SDK installed.
- Missing API key produces a clear error only when segmentation is invoked.
- Request body includes model, messages, reasoning controls, `max_tokens`, and
  structured response format.
- Retryable HTTP failures retry once by default.
- Permanent failures do not retry.
- Length-limit responses produce a specific diagnostic.
- Token usage is extracted when available.
- Span validation rejects invalid, overlapping, out-of-range, empty, unordered,
  or non-text-covering spans.
- Tests use fake clients and make no live Sarvam calls.

### Verification

- Unit tests for successful segmentation, invalid JSON, invalid spans,
  retryable failures, permanent failures, length-limit diagnostics, token usage,
  throttling, and request body shape.

## Stage 4: Chapter Metadata Integration

### Goal

Run paragraph segmentation during chapter splitting and store validated spans in
chapter metadata.

### Scope

- Call the segmenter after writing the canonical raw chapter `.txt`.
- Store segmentation status and spans in chapter metadata.
- Do not write formatted text artifacts.
- Preserve canonical raw text and DOCX behavior.
- Add chapter metadata schema support.
- Add checksum binding.
- Add disabled, segmented, skipped-unchanged, and failed states.
- Keep `continue_on_error` behavior.

### Acceptance Criteria

- Segmentation runs only when `paragraph_segmentation.enabled` is true.
- Successful segmentation stores spans in metadata.
- Metadata records `source_text_sha256`, model, status, attempts, throttling,
  warning, and token usage.
- Failed segmentation records status `failed` and warning, without failing the
  job when `continue_on_error` is true.
- No `*.formatted.json` or `*.formatted.md` files are written.
- Existing chapter text, DOCX, and base metadata outputs remain valid.

### Verification

- Tests for disabled segmentation.
- Tests for successful segmentation metadata.
- Tests for failure with `continue_on_error: true`.
- Tests for fail-fast behavior with `continue_on_error: false`.
- Tests confirming no formatted artifacts are created.

## Stage 5: Checksum-Based Reuse

### Goal

Avoid Sarvam calls when existing metadata already contains valid spans for the
unchanged raw chapter text.

### Scope

- Implement reuse based on metadata `source_text_sha256`.
- Validate existing spans before reuse.
- Mark reused chapters as `skipped-unchanged`.
- Regenerate when checksum differs, spans are invalid, status is failed, or
  spans are missing.
- Define R2 reuse behavior explicitly.

### Recommended R2 Behavior

For normal R2 content-preparation runs, do not claim reuse from remote metadata
unless previous metadata has been intentionally materialized into the current
local subject tree or a dedicated future cache exists.

The retry command can reuse R2 metadata directly because it explicitly reads R2
metadata and raw text as durable inputs.

### Acceptance Criteria

- Valid local metadata spans with matching checksum are reused without Sarvam.
- Invalid spans or checksum mismatch cause regeneration.
- Reuse records status `skipped-unchanged`.
- R2 reuse limitations are documented and tested.

### Verification

- Unit tests for matching checksum reuse.
- Unit tests for checksum mismatch.
- Unit tests for invalid span regeneration.
- Tests proving R2 jobs do not silently claim reuse from unavailable remote
  state.

## Stage 6: Progress Reporting And Operator Output

### Goal

Add clear operator progress during chapter segmentation and R2 operations.

### Scope

- Add or carry forward a small progress reporter.
- Report chapter-level segmentation progress.
- Report Sarvam attempts and retry sleeps.
- Report success span counts.
- Report skipped unchanged.
- Report failures.
- Report R2 milestones.

### Acceptance Criteria

- Long-running segmentation runs are visibly progressing.
- Output includes chapter index and total.
- Output never includes secrets, request bodies, or full source text.
- Tests cover representative progress output.

### Verification

- Focused progress reporter tests.
- Content-preparation tests.

## Stage 7: Run Audit Reports And Token Accounting

### Goal

Write durable JSON and Markdown audit reports summarizing paragraph segmentation
outcomes and cost evidence.

### Scope

- Add or carry forward run report generation.
- Include segmentation status counts.
- Include per-chapter span count and status.
- Include failed chapters and retry candidates.
- Include retry-exhausted chapters.
- Include token usage totals and per-chapter token usage.
- Include request attempts, retry counts, and throttle sleep totals.
- Upload reports with R2 subject artifacts.

### Acceptance Criteria

- Each successful content-preparation run writes audit reports under
  `run_reports/`.
- Reports summarize paragraph segmentation outcomes.
- Reports include token usage sufficient to evaluate output-token economy.
- Reports exclude secrets, request bodies, and full chapter text.
- R2 destinations upload reports with the subject artifact tree.

### Verification

- Tests for report generation with segmented, failed, skipped, and disabled
  chapters.
- Tests for token usage aggregation.
- Tests for R2 publish path including reports.

## Stage 8: R2 Retry Command For Failed Segmentation

### Goal

Add an operator command to retry failed paragraph segmentation without rerunning
DOCX conversion or full content preparation.

### Scope

- Add `gurubodh-utils retry-paragraph-segmentation`.
- Require R2 destination for first implementation.
- List chapter metadata JSON objects from the configured R2 subject prefix.
- Select failed chapters with `retry_attempts < 3`.
- Treat missing `retry_attempts` as `0`.
- Download canonical raw `.txt` artifacts.
- Retry Sarvam segmentation.
- Upload updated metadata on success or failure.
- Do not write formatted artifacts.
- Support `--dry-run`, `--chapter`, `--chapters`, and default failed-only
  selection.
- Report retry-exhausted chapters.

### Acceptance Criteria

- Dry-run lists selected, skipped, and retry-exhausted chapters without Sarvam
  calls or R2 writes.
- Successful retry updates metadata with spans and status `segmented`.
- Failed retry increments `retry_attempts`, keeps status `failed`, records the
  latest warning, and uploads metadata.
- Retry-exhausted chapters are reported but not retried.
- Missing raw text artifacts are skipped with clear reasons.
- Existing valid spans can repair stale failed metadata when checksum matches.

### Verification

- Fake-R2 tests for discovery, selection, dry-run, success, failure, retry cap,
  missing raw text, invalid metadata, and metadata upload order.
- Full content-preparation tests.

## Stage 9: Documentation And Manual Verification

### Goal

Document the final operator workflow and verify the implementation with a
representative Sarvam-backed run.

### Scope

- Update `tools/content-preparation/README.md`.
- Update `docs/schemas.md`.
- Add or update safe sample configs with segmentation disabled by default.
- Document enabling segmentation with `SARVAM_API_KEY`.
- Document span semantics and on-demand rendering.
- Document retry command.
- Document known limitations.
- Run unit tests.
- Run a representative manual Sarvam/R2 job when credentials and source files
  are available.

### Acceptance Criteria

- Normal local sample runs do not require Sarvam credentials.
- Documentation explains that no formatted text artifacts are produced.
- Documentation explains how spans are rendered on demand.
- Documentation explains checksum validation and failure behavior.
- Verification results are reported.

### Verification

```bash
tools/content-preparation/.venv/bin/python -m unittest discover -s tools/content-preparation/tests
git diff --check
```

Manual verification, when credentials are available:

```bash
gurubodh-utils run --config jobs/001_aacharan_shaastra.r2.json --overwrite
gurubodh-utils retry-paragraph-segmentation --config jobs/001_aacharan_shaastra.r2.json --dry-run
```

Expected manual checks:

- metadata contains paragraph spans;
- no formatted JSON/Markdown artifacts are produced;
- spans render readable paragraphs from raw text;
- token usage is far lower than full-text formatting output;
- failed chapters appear as retry candidates;
- reports contain no secrets or full chapter text.

## Risks

- Sarvam may return character indices based on a different Unicode indexing
  model than Python string indices.
- Root-array structured output may not be supported as reliably as an object
  wrapper.
- Paragraph boundaries may be linguistically reasonable but not exact enough for
  operator expectations.
- Span maps are brittle if raw text changes without metadata regeneration.
- `max_tokens: 1024` may be too low for very long chapters with many paragraph
  spans.
- R2 metadata rewrites can race if multiple operators run retry commands at the
  same time.

## Risk Mitigations

- Validate spans against the exact Python string before accepting them.
- Consider switching to object-wrapper output if root-array output is unstable.
- Store `index_unit` and `span_semantics` explicitly.
- Refuse to render spans when checksum mismatches.
- Keep `max_tokens` configurable and record token usage.
- Report retry attempts and exhausted chapters clearly.
- Document that concurrent retry runs are not coordinated in the first version.

## Suggested GitHub Issue Breakdown

1. `docs(tasks): define Sarvam paragraph segmentation metadata task`
2. `feat(content-prep): add paragraph segmentation config schema contract`
3. `feat(content-prep): add Sarvam paragraph segmenter module`
4. `feat(content-prep): store paragraph spans in chapter metadata`
5. `feat(content-prep): reuse paragraph spans for unchanged chapter text`
6. `feat(content-prep): add paragraph segmentation progress reporting`
7. `feat(content-prep): add paragraph segmentation audit reports and token usage`
8. `feat(content-prep): add retry command for failed paragraph segmentation`
9. `docs(content-prep): document paragraph segmentation workflow and verification`

## Definition Of Done

- Paragraph segmentation can be enabled per conversion job.
- Sarvam returns only compact span data, not document text.
- Validated spans are stored in chapter metadata.
- Canonical raw text remains unchanged and authoritative.
- No formatted text artifacts are generated.
- Metadata carries checksum, status, diagnostics, attempts, throttling, retry
  attempts, and token usage.
- Audit reports make output-token economy measurable.
- Failed R2-backed segmentation can be retried without rerunning full content
  preparation.
- Tests cover config, segmenter parsing, span validation, metadata, reuse,
  reports, and retry behavior.
