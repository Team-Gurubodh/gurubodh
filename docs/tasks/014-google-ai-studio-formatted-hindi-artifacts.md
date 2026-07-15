# Task-014: Google AI Studio Formatted Hindi Chapter Artifacts

<record_type>task_history</record_type>
<status>proposed (draft - to be reviewed) </status>
<date>2026-07-15</date>
<owners>Gurubodh maintainers</owners>
<github_issue>https://github.com/Team-Gurubodh/gurubodh/issues/109</github_issue>
<baseline_tag>task-013-complete-before-formatting</baseline_tag>
<baseline_commit>c34d7c6994fd33e7d4fa55110c418383192d241b</baseline_commit>
<reference_sarvam_tag>task-014-sarvam-implementation</reference_sarvam_tag>

## Goal

Define the requirements for integrating Google AI Studio Gemini formatting into
`gurubodh-utils` so prepared chapter artifacts include display-friendly
formatted Hindi text in addition to the canonical raw chapter text, chapter
metadata JSON, and chapter MS Word output.

The formatted output is intended for quick display and review. It must not
replace the canonical extracted chapter `.txt` artifact used for ingestion,
integrity checks, or future processing.

This task is intentionally based on the preserved Task 013 baseline where Task
014 formatting work is absent. The earlier Sarvam implementation remains
preserved separately for reference and comparison, but this task should design
the formatter as a Google AI Studio native implementation rather than carrying
forward Sarvam-specific API, model, dependency, or metadata names.

## Context

The current content-preparation pipelines write chapter artifacts under:

```text
{subject_dir}/chapters/msword/
{subject_dir}/chapters/text_and_metadata/
```

For each chapter, `gurubodh-utils` currently creates:

- a chapter `.docx` artifact;
- a canonical raw chapter `.txt` artifact;
- a chapter metadata `.json` artifact.

For R2-backed jobs, the pipeline first writes artifacts to a temporary subject
directory and then uploads the whole subject artifact tree to Cloudflare R2.
This makes chapter splitting the best integration point for formatted Hindi
artifact generation: the formatter can write local/temp files next to the
existing text and metadata outputs, and the existing R2 publish step can upload
them without a separate R2 batch processor.

The formatting job is deliberately narrow. It should preserve the original
Hindi Devanagari content, add punctuation where useful, and split the text into
readable paragraphs. It should not depend on deep semantic interpretation,
religious commentary, summarization, translation, title generation, or
metadata-generation behavior.

Google AI Studio / Gemini is suitable for evaluation here because the desired
task is text normalization and layout, not authoritative doctrinal analysis.
The implementation should use native Gemini API capabilities, especially
structured JSON output, while keeping the prompt and post-response validation
strict.

## Decisions

- Add formatted Hindi output as a content-preparation artifact, not as a CMS
  write operation.
- Keep the raw chapter `.txt` artifact canonical and unchanged.
- Generate two formatted files for each successfully formatted chapter:
  - `*.formatted.json`;
  - `*.formatted.md`.
- Store formatted artifacts beside the existing chapter text and metadata files
  under `chapters/text_and_metadata/`.
- Enable formatting only when the conversion job has
  `formatting.enabled: true`.
- Use Google AI Studio / Gemini as the formatter provider for this task.
- Prefer the native Google GenAI SDK and Gemini API shape over the
  OpenAI-compatible endpoint for the first implementation.
- Use a lightweight Gemini model by default because this task is punctuation
  and paragraphing, not high-reasoning analysis.
- Do not configure high thinking effort by default. If a chosen Gemini model
  supports thinking controls, configure the lowest appropriate value for this
  workflow, such as `low` or `minimal` when supported by the selected model.
- Require structured JSON output via Gemini `response_format` with a JSON
  schema, and still validate the returned JSON defensively in code.
- Record the number of paragraphs returned by Gemini in both the formatted JSON
  artifact and the chapter metadata `formatting` section.
- A formatting failure must not fail the overall content-preparation job.
  Instead, the job should complete with clear warnings and metadata that makes
  the missing or failed formatted artifact state visible.
- Do not ask Gemini to create canonical chapter titles. Chapter identity and
  titles remain owned by Gurubodh naming and metadata.
- Process one chapter at a time by default.
- Use pacing between Gemini requests, with a default delay of 5 seconds unless
  later testing proves a better value.
- Regenerate formatted output the first time, and on later runs only when the
  raw chapter text checksum changes.
- Preserve the GitHub Issue-first workflow for implementation work.

## Proposed Artifact Shape

For a chapter whose existing base name is:

```text
CAT001-SUB002-some-title-v01.00-001
```

the target files should be:

```text
chapters/msword/
  CAT001-SUB002-some-title-v01.00-001.docx

chapters/text_and_metadata/
  CAT001-SUB002-some-title-v01.00-001.txt
  CAT001-SUB002-some-title-v01.00-001.json
  CAT001-SUB002-some-title-v01.00-001.formatted.json
  CAT001-SUB002-some-title-v01.00-001.formatted.md
```

`*.formatted.json` should preserve the structured formatter output and
formatter provenance. At minimum, it should include:

```json
{
  "schema_version": "1.0.0",
  "provider": "google-ai-studio",
  "model": "gemini-2.5-flash-lite",
  "fallback_model_used": null,
  "thinking_level": "low",
  "source_text_sha256": "...",
  "status": "formatted",
  "paragraph_count": 2,
  "paragraphs": [
    "..."
  ]
}
```

When formatting fails but the main job continues, the implementation should
omit display-ready formatted artifact files and record failure state in chapter
metadata. Failure JSON artifacts are not part of the first implementation,
because they are easy to confuse with display-ready formatted text.

`*.formatted.md` should be display-friendly Markdown built from the formatted
paragraphs:

```markdown
Paragraph one.

Paragraph two.
```

The Markdown artifact should not add AI-generated headings unless a future task
explicitly approves display-title generation.

## Proposed Job Config Shape

Add an optional `formatting` object to the conversion job schema:

```json
{
  "formatting": {
    "enabled": true,
    "provider": "google-ai-studio",
    "model": "gemini-2.5-flash-lite",
    "fallback_model": "gemini-2.5-flash",
    "output_formats": ["json", "markdown"],
    "continue_on_error": true,
    "delay_seconds": 5,
    "max_retries": 3,
    "regenerate": "when-source-checksum-changes",
    "thinking_level": "low",
    "max_output_tokens": 8192
  }
}
```

Expected validation rules:

- `formatting` is optional.
- If omitted, formatting is disabled.
- `formatting.enabled` must be boolean when present.
- `provider` must initially support only `google-ai-studio`.
- `model` should default to `gemini-2.5-flash-lite`.
- `fallback_model` should default to `gemini-2.5-flash` when fallback behavior
  is enabled.
- `output_formats` should initially support `json` and `markdown`.
- `continue_on_error` should default to `true` for this workflow.
- `delay_seconds` should default to `5`.
- `max_retries` should be a small bounded integer.
- `regenerate` should support the initial value
  `when-source-checksum-changes`.
- `thinking_level` should default to a low-effort setting for models that
  support it. The implementation must not default to high thinking effort.
- `max_output_tokens` should reserve enough generation budget for a near-full
  copy of the input with punctuation and paragraph breaks.

## Schema Versioning And Validation

The future implementation changes the public content-preparation contracts, so
schema versioning must be handled deliberately.

Expected schema version changes:

- Bump `conversion_job.schema.json` from `1.2.0` to `1.3.0`.
- Bump `chapter_metadata.schema.json` from `1.2.0` to `1.3.0`.
- Update the corresponding schema-version constants in code.
- Update docs and tests in the same implementation change.

Rationale:

- The `formatting` job config block is optional and backward-compatible, but it
  expands the conversion job contract.
- Formatted artifact references and formatting status are optional for jobs that
  do not enable formatting, but generated metadata can now carry a richer
  artifact contract.
- The metadata `formatting.paragraph_count` field gives downstream tools and
  reviewers a compact signal about formatter behavior without opening the
  formatted artifact.
- Downstream tools should be able to identify which schema contract produced or
  validated an artifact.

Existing conversion jobs should not require manual edits from maintainers. The
implementation should provide an automatic migration path from `1.2.0` job
configs to `1.3.0`.

Migration requirements:

- Provide a `gurubodh-utils` migration command or equivalent documented command
  that updates existing `schema_version: "1.2.0"` job configs to
  `schema_version: "1.3.0"`.
- Preserve all existing job fields and formatting.
- Add no `formatting` block by default, or add it only with
  `enabled: false`, so migrated jobs keep their current behavior.
- Support a dry-run or preview mode that reports which files would change.
- Support an apply mode that writes the migrated files.
- Refuse or warn on unsupported schema versions instead of silently rewriting
  unknown files.
- Cover migration behavior with tests for local sample jobs.

Validation requirements:

- Validate `1.3.0` job configs with formatting omitted.
- Validate `1.3.0` job configs with formatting disabled.
- Validate `1.3.0` job configs with formatting enabled.
- Reject invalid formatting providers, invalid output formats, invalid retry
  values, invalid thinking levels, invalid output token values, and invalid
  regeneration modes.
- Validate chapter metadata with formatting disabled and no formatted artifacts.
- Validate chapter metadata with successful formatted artifacts.
- Validate chapter metadata with formatting failure status and no display-ready
  formatted Markdown artifact.
- Validate `formatting.paragraph_count` as either `null` or a non-negative
  integer, with successful formatting requiring a positive value.
- Keep backward compatibility expectations explicit for any consumer that still
  reads `1.2.0` metadata during the transition.

## Metadata Requirements

Chapter metadata should discoverably reference formatted artifacts when they
exist. The implementation should update both metadata generation and
`chapter_metadata.schema.json`.

The `files` section should add optional formatted artifact names:

```json
{
  "files": {
    "metadata_filename": "...json",
    "text_filename": "...txt",
    "msword_filename": "...docx",
    "formatted_json_filename": "...formatted.json",
    "formatted_markdown_filename": "...formatted.md"
  }
}
```

The `storage.artifacts` section should add optional storage references:

```json
{
  "storage": {
    "artifacts": {
      "formatted_json": {
        "backend": "r2",
        "bucket": "...",
        "key": "...",
        "url": null
      },
      "formatted_markdown": {
        "backend": "r2",
        "bucket": "...",
        "key": "...",
        "url": null
      }
    }
  }
}
```

The `integrity.artifacts` section should add SHA-256 checksums for formatted
artifact bytes when those artifacts are written:

```json
{
  "integrity": {
    "artifacts": {
      "text": {
        "algorithm": "sha256",
        "encoding": "UTF-8",
        "line_endings": "LF",
        "scope": "artifact-bytes",
        "value": "..."
      },
      "formatted_json": {
        "algorithm": "sha256",
        "encoding": "UTF-8",
        "line_endings": "LF",
        "scope": "artifact-bytes",
        "value": "..."
      },
      "formatted_markdown": {
        "algorithm": "sha256",
        "encoding": "UTF-8",
        "line_endings": "LF",
        "scope": "artifact-bytes",
        "value": "..."
      }
    }
  }
}
```

Metadata should also expose formatting status without making the entire chapter
invalid when formatting fails:

```json
{
  "formatting": {
    "enabled": true,
    "provider": "google-ai-studio",
    "model": "gemini-2.5-flash-lite",
    "fallback_model": "gemini-2.5-flash",
    "model_used": "gemini-2.5-flash-lite",
    "thinking_level": "low",
    "status": "formatted",
    "warning": null,
    "source_text_sha256": "...",
    "paragraph_count": 12
  }
}
```

Allowed statuses should include at least:

- `disabled`;
- `formatted`;
- `skipped-unchanged`;
- `failed`.

`paragraph_count` behavior:

- `disabled`: `paragraph_count` must be `null`.
- `formatted`: `paragraph_count` must equal the number of returned paragraphs.
- `skipped-unchanged`: `paragraph_count` should be read from the reusable
  formatted JSON artifact when available.
- `failed`: `paragraph_count` must be `null` unless a future retry workflow can
  safely preserve a valid previous count for the same source checksum.

## Google AI Studio Prompt Requirements

The formatter should use strict Hindi preservation instructions. The system
instruction should focus only on punctuation and paragraphing:

```text
आप एक विशेषज्ञ हिंदी संपादक हैं। आपका कार्य दिए गए कच्चे हिंदी देवनागरी पाठ को केवल पढ़ने योग्य बनाना है।

मुख्य नियम:
1. मूल पाठ का अर्थ, भाषा, क्रम और शब्दावली सुरक्षित रखें।
2. अनुवाद न करें।
3. संक्षेप न करें।
4. नया विचार, व्याख्या, शीर्षक, टिप्पणी या निष्कर्ष न जोड़ें।
5. किसी भी वाक्य, पंक्ति, नाम, मंत्र, श्लोक, उद्धरण या धार्मिक/दार्शनिक शब्द को हटाएँ नहीं।
6. जहाँ आवश्यक हो वहाँ केवल विराम चिन्ह जोड़ें: पूर्ण विराम (।), अल्पविराम (,), प्रश्नवाचक चिन्ह (?), द्विबिंदु (:), अर्धविराम (;), उद्धरण चिह्न।
7. विषय या भाव में स्वाभाविक बदलाव के आधार पर पाठ को छोटे, पठनीय पैराग्राफों में बाँटें।
8. पैराग्राफ बनाने के लिए पाठ का क्रम न बदलें।
9. वर्तनी या व्याकरण सुधार केवल तभी करें जब वह स्पष्ट टाइपिंग/OCR त्रुटि हो और अर्थ न बदले।
10. संस्कृत, हिंदी, मराठी, पारिभाषिक, धार्मिक और नाम-संबंधी शब्दों को यथावत रखें।
11. यदि पाठ में क्रमांक, प्रबोधन संख्या, अध्याय संकेत, वक्ता संकेत या शीर्षक जैसा भाग हो, तो उसे सुरक्षित रखें।

आपको केवल एक वैध JSON ऑब्जेक्ट लौटाना है। JSON में बिल्कुल ये कुंजियाँ हों:

{
  "paragraphs": [
    "पहला पैराग्राफ",
    "दूसरा पैराग्राफ"
  ]
}

आउटपुट में JSON के अलावा कोई अतिरिक्त टेक्स्ट, Markdown, टिप्पणी या ```json बैकटिक्स न दें।
```

The API request must use Gemini structured output support in addition to the
prompt. The target response format should be equivalent to:

```json
{
  "type": "text",
  "mime_type": "application/json",
  "schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["paragraphs"],
    "properties": {
      "paragraphs": {
        "type": "array",
        "minItems": 1,
        "items": {
          "type": "string",
          "minLength": 1
        }
      }
    }
  }
}
```

The implementation should still parse and validate the response after the API
returns it. Structured output reduces malformed responses, but it does not
replace defensive validation in `gurubodh-utils`.

## Gemini API Requirements

The first implementation should use the native Google GenAI SDK with Google AI
Studio API-key authentication.

Expected API behavior:

- Read credentials from `GEMINI_API_KEY` or another explicitly documented
  Google AI Studio environment variable.
- Keep the SDK dependency optional so non-formatting jobs do not require Google
  dependencies at import time.
- Use a native Gemini call that supports:
  - model selection;
  - input text;
  - `response_format` with `application/json` and JSON schema;
  - generation configuration for output-token and thinking controls.
- Configure thinking effort as low, minimal, or model-default-off for this
  workflow. High thinking effort must require explicit operator configuration.
- Preserve response usage diagnostics when available, especially input tokens,
  output tokens, and thought tokens, but do not make usage metadata mandatory
  for the first artifact contract.
- Do not use Google Search grounding, URL context, tools, or code execution for
  this formatter.

## Token And Rate-Limit Handling

The Gemini context window must include:

- system instruction tokens;
- structured-output schema tokens;
- input chapter text tokens;
- generated formatted output tokens;
- any thought-token budget used by the configured model.

Because the output is a near-full copy of the input with punctuation and
paragraph breaks, the implementation must leave enough output budget instead of
treating the entire model context window as input capacity.

Implementation requirements:

- Estimate request size before calling Gemini.
- Process one chapter per request when the chapter fits safely.
- If a chapter is too large for the configured model, either:
  - use the configured fallback model if it has a larger safe budget; or
  - split into smaller formatting chunks with deterministic reassembly.
- Preserve paragraph order across chunks.
- Warn clearly when formatting is skipped because a chapter cannot be safely
  processed.
- Sleep between Gemini calls using the configured `delay_seconds`.
- Retry retryable API failures such as rate-limit or temporary service errors.
- Do not retry permanent failures such as invalid credentials or invalid
  response schema beyond the configured validation path.
- Treat output-token exhaustion as a distinct diagnostic condition rather than
  a generic invalid JSON error.

## Checksum And Regeneration Behavior

The raw chapter `.txt` artifact checksum should drive formatting reuse.

Expected behavior:

- First run with formatting enabled writes formatted artifacts when Gemini
  succeeds.
- Later runs should skip Gemini formatting for a chapter if:
  - the raw chapter text checksum is unchanged; and
  - matching formatted artifacts already exist; and
  - formatted artifact metadata records the same source text checksum.
- If the raw chapter text checksum changes, regenerate formatted artifacts.
- If formatted artifacts are missing or invalid, regenerate them even when raw
  text is unchanged.
- If formatting fails during regeneration, preserve the canonical raw text and
  metadata outputs and report a warning.

For local destinations, checksum reuse can read existing files from the local
subject output directory when `--overwrite` behavior permits. For R2
destinations, the implementation should define whether reuse is based on
materialized previous artifacts from R2, current metadata, or a future cache
layer before writing code.

## Error Handling

Formatting is useful but non-authoritative. Failure must not corrupt or block
canonical content-preparation outputs.

Required behavior:

- Missing Google AI Studio API credentials should warn and skip formatting when
  `formatting.enabled` is true and `continue_on_error` is true.
- Invalid Gemini responses should warn, record failure status, and continue
  when `continue_on_error` is true.
- Structured-output schema failures should warn, record failure status, and
  continue when `continue_on_error` is true.
- Rate-limit exhaustion after retries should warn, record failure status, and
  continue.
- Output-token exhaustion should include a clear diagnostic and should not write
  display-ready formatted artifacts.
- The job should still fail for canonical preparation errors such as invalid
  DOCX input, failed chapter splitting, invalid required config, or R2 upload
  failures.
- Warnings should include chapter number and artifact base name.
- The final CLI summary should report counts:
  - formatted;
  - skipped unchanged;
  - failed;
  - disabled.

## Implementation Plan

### Stage 1 - Configuration And Schema Contract

1. Extend `conversion_job.schema.json` with optional `formatting`.
2. Bump the conversion job schema version to `1.3.0`.
3. Extend `config.py` validation for the new formatting block.
4. Add tests for omitted formatting config, disabled formatting, enabled Google
   formatting, invalid providers, invalid model names, invalid thinking levels,
   invalid output token values, and defaults.
5. Add an automatic migration command or equivalent documented command for
   converting `1.2.0` job configs to `1.3.0` without manual editing.

### Stage 2 - Formatter Module

1. Add a Google AI Studio formatter module under `gurubodh_utils`.
2. Keep Google GenAI SDK import lazy so existing non-formatting jobs do not
   require Google dependencies at import time.
3. Read Google AI Studio credentials from the documented environment variable.
4. Implement native Gemini structured output with `response_format`.
5. Implement strict JSON parsing and validation.
6. Implement `paragraph_count` derivation from validated paragraphs.
7. Implement configured delay and retry behavior.
8. Add unit tests with a fake Google GenAI client.

### Stage 3 - Chapter Artifact Generation

1. Hook formatting into chapter splitting after raw chapter text is written and
   before metadata is finalized.
2. Generate `*.formatted.json` and `*.formatted.md` when formatting succeeds.
3. Include `paragraph_count` in the formatted JSON artifact.
4. Track formatting status, paragraph count, and warnings per chapter.
5. Ensure R2 upload continues to use the existing publish-all-artifacts flow.

### Stage 4 - Metadata And Integrity

1. Extend `chapter_metadata.schema.json`.
2. Bump the chapter metadata schema version to `1.3.0`.
3. Extend metadata generation to include formatted artifact file names, storage
   references, checksums, formatting status, and `formatting.paragraph_count`.
4. Preserve backward compatibility for jobs that do not enable formatting.
5. Add schema and metadata unit tests.

### Stage 5 - Reuse And Regeneration

1. Implement source-text-checksum comparison.
2. Skip Gemini calls for unchanged chapters when valid formatted artifacts
   already exist.
3. Carry `paragraph_count` forward from reusable formatted JSON artifacts.
4. Add local reuse tests.
5. Define and test the R2 reuse strategy before depending on it in production.

### Stage 6 - Documentation And Verification

1. Update `tools/content-preparation/README.md` with formatting config,
   environment variables, artifact shape, and failure semantics.
2. Update `docs/schemas.md` if schema ownership or shape changes require it.
3. Add a small sample job config with formatting disabled or enabled only if it
   is safe for normal local runs.
4. Run the content-preparation test suite.
5. Manually test one representative chapter with Google AI Studio credentials
   outside CI.

Automated verification should use the content-preparation virtual environment:

```bash
tools/content-preparation/.venv/bin/python -m unittest discover -s tools/content-preparation/tests
```

Manual Google AI Studio verification remains an operator-run check because it
requires local source documents and private Google AI Studio API credentials.

## Acceptance Criteria

- The future implementation is controlled by `formatting.enabled`.
- `google-ai-studio` is the configured formatter provider.
- `gemini-2.5-flash-lite` is the default primary model unless manual
  verification identifies a better lightweight default.
- A fallback Gemini model is configurable.
- High thinking effort is not used by default.
- Gemini structured JSON output / `response_format` is used for the formatter
  response contract.
- The canonical raw chapter `.txt` output remains unchanged.
- Successful formatting writes both `*.formatted.json` and `*.formatted.md`.
- Formatted artifacts are referenced from chapter metadata when present.
- Formatted artifacts include integrity checksums.
- Formatted JSON and chapter metadata record `paragraph_count`.
- Conversion job and chapter metadata schemas are bumped to `1.3.0`.
- Existing `1.2.0` conversion job configs can be migrated to `1.3.0` without
  manual editing.
- The migration path has dry-run/preview behavior and tests.
- `1.3.0` config and metadata validation covers formatting enabled, disabled,
  successful, skipped, and failed states.
- Failed formatting does not fail the content-preparation job when
  `continue_on_error` is true.
- The CLI reports formatting warnings and summary counts.
- Formatting is skipped for unchanged raw chapter text when valid matching
  formatted artifacts already exist.
- Token-limit, thought-token, structured-output, and rate-limit handling are
  covered by tests or documented manual verification.

## Non-Goals

- Do not ingest formatted artifacts into Strapi in the first implementation.
- Do not replace canonical chapter text with Gemini output.
- Do not generate authoritative chapter titles with Gemini.
- Do not implement semantic summaries, tags, descriptors, embeddings, or RAG
  chunking in this task.
- Do not use Google Search grounding, URL context, tools, or code execution for
  formatting.
- Do not introduce a separate standalone R2 batch processor for formatted text.
- Do not keep Sarvam-specific API names, environment variables, dependencies,
  or model defaults in the Google implementation.

## Follow-Up

- Evaluate `gemini-2.5-flash-lite` versus `gemini-2.5-flash` on representative
  Gurubodh chapters before enabling formatting broadly.
- Compare Google AI Studio output with the preserved Sarvam implementation for
  paragraph quality, punctuation quality, text preservation, JSON reliability,
  latency, and cost.
- Add chunked formatting for chapters that hit output-token limits.
- Add a durable retry workflow for formatter failures after the basic Google
  implementation is accepted.
