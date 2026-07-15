# Content Preparation

Python utilities for preparing Gurubodh CMS-ready content from DOCX source files.

## Setup

Run these commands from the monorepo root:

```bash
cd tools/content-preparation
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
gurubodh-utils run --config jobs/002_spand_rahasya.local.json
```

## What These Commands Do

`cd tools/content-preparation` moves into this Python tool project.

`python3 -m venv .venv` creates a local virtual environment named `.venv`.

`. .venv/bin/activate` activates the virtual environment so dependencies and console commands are isolated to this project.

`pip install -e .` installs the package in editable mode. This exposes the `gurubodh-utils` command while keeping it linked to the source files in this directory.

`gurubodh-utils run --config jobs/002_spand_rahasya.local.json` runs a sample local content-preparation job.

Existing output is not archived. If the configured local output directory or R2
objects already exist, re-run with `--overwrite` when you intentionally want to
replace them:

```bash
gurubodh-utils run --config jobs/002_spand_rahasya.local.json --overwrite
```

## Project Root Detection

The CLI detects this tool's root by finding both:

```text
config/conversion_job.schema.json
jobs/
```

If running from another directory, pass the root explicitly:

```bash
gurubodh-utils run \
  --project-root /Users/rajeev/Applications/gurubodh/tools/content-preparation \
  --config jobs/002_spand_rahasya.local.json
```

## Job Schema Migration

Conversion job configs use `schema_version`. To preview migration from
`1.2.0` configs to the current `1.3.0` schema without writing files:

```bash
gurubodh-utils migrate-configs jobs/002_spand_rahasya.local.json
```

To apply the migration:

```bash
gurubodh-utils migrate-configs --apply jobs/002_spand_rahasya.local.json
```

The migration updates the schema version, preserves existing fields, and adds
the default formatting configuration with formatting disabled, so
migrated jobs continue to behave like `1.2.0` jobs until you explicitly enable
formatting:

```json
{
  "formatting": {
    "enabled": false,
    "provider": "sarvam",
    "model": "sarvam-30b",
    "fallback_model": "sarvam-105b",
    "output_formats": ["json", "markdown"],
    "continue_on_error": true,
    "delay_seconds": 4,
    "max_retries": 1,
    "regenerate": "when-source-checksum-changes",
    "reasoning_effort": null,
    "max_tokens": 4096
  }
}
```

Set `formatting.enabled` to `true` when you want the job to call Sarvam and
write formatted chapter artifacts. If a `1.3.0` config is already current but
omits the explicit `formatting` block, `migrate-configs` can also preview or add
the same disabled defaults without changing the schema version. The migration
validates `1.2.0` configs
against `config/conversion_job.1.2.0.schema.json` before previewing or applying
changes. Unsupported schema versions and invalid `1.2.0` configs are refused
instead of silently rewritten.

For current `1.3.0` configs that already have a `formatting` block, the
migration also normalizes missing formatting defaults such as
`reasoning_effort` and `max_tokens` without changing explicitly configured
values like `enabled` or `continue_on_error`.

## Optional Formatting Configuration

Schema `1.3.0` adds an optional `formatting` block for Sarvam Hindi formatter
integration. If the block is omitted, formatting is disabled.

```json
{
  "formatting": {
    "enabled": true,
    "provider": "sarvam",
    "model": "sarvam-30b",
    "fallback_model": "sarvam-105b",
    "output_formats": ["json", "markdown"],
    "continue_on_error": true,
    "delay_seconds": 4,
    "max_retries": 1,
    "regenerate": "when-source-checksum-changes",
    "reasoning_effort": null,
    "max_tokens": 4096
  }
}
```

When formatting is enabled, chapter splitting calls Sarvam after the canonical
raw chapter `.txt` artifact is written. A successful formatting response writes
formatted artifacts beside the chapter text and metadata files:

```text
chapters/text_and_metadata/
  CAT020_SUB129_spand-rahasya_001_v01.01.txt
  CAT020_SUB129_spand-rahasya_001_v01.01.json
  CAT020_SUB129_spand-rahasya_001_v01.01.formatted.json
  CAT020_SUB129_spand-rahasya_001_v01.01.formatted.md
```

The canonical raw chapter `.txt` artifact remains unchanged. The formatted JSON
artifact preserves formatter provenance and paragraphs; the formatted Markdown
artifact is display-friendly paragraph text without generated headings.

If formatting fails and `continue_on_error` is `true`, the job prints a warning,
omits formatted files for that chapter, and continues with the canonical chapter
artifacts. If `continue_on_error` is `false`, the job fails on the formatting
error.

Chapter metadata records formatted artifact filenames, storage references,
formatted artifact integrity checksums, and per-chapter formatting status when
formatted files are produced.

When `regenerate` is `when-source-checksum-changes`, the formatter compares the
raw chapter text SHA-256 with `source_text_sha256` in an existing
`*.formatted.json` artifact. If the checksum matches and the requested formatted
artifacts are present and valid, the Sarvam call is skipped and chapter metadata
records `formatting.status` as `skipped-unchanged`. If the checksum differs, the
formatted JSON is invalid, the formatted status is not display-ready, or a
requested formatted artifact is missing, the formatter regenerates the formatted
artifacts.

For local destinations, reruns with `--overwrite` preserve existing
`*.formatted.json` and `*.formatted.md` files long enough for checksum-based
reuse validation, while other generated artifacts are replaced. For R2
destinations, jobs build artifacts in a temporary local subject tree before
upload. Stage 5 does not download previously uploaded R2 artifacts for reuse; R2
jobs only reuse formatted artifacts that have already been materialized into the
current local artifact tree by a future cache or restore step.

Sarvam formatting reads the API key from `SARVAM_API_KEY` when formatting is
enabled. Formatter chat completions use Sarvam's direct HTTP chat-completions
endpoint and send a structured `response_format` request body with
`type: "json_schema"` and `strict: true`. The schema requires a non-empty
`paragraphs` array, and the formatter treats Markdown-fenced or otherwise
repaired JSON as an invalid Sarvam response instead of silently normalizing it.

Formatter chat completions default `reasoning_effort` to `null` and
`max_tokens` to `4096`. This disables Sarvam reasoning output for the formatter
call and reserves the completion budget for the JSON formatter response.
`delay_seconds` defaults to `4` and is applied before every Sarvam request after
the first request in a run, including retry attempts. This keeps sequential
formatter throughput below 20 requests per minute.
`max_retries` defaults to `1`, which means one retry after the initial call.
The formatter hard-caps retries at one even when an older config sets a higher
value.

```bash
pip install -e .
```

Put the key in your shell environment before running the tool:

```bash
export SARVAM_API_KEY=...
```

You may also keep it in a local untracked `.env` file for your own shell setup,
but do not commit API keys. Sarvam's API base URL is `https://api.sarvam.ai`;
normal formatter usage does not require the Sarvam Python SDK, so you should
not need to configure the URL separately.

Formatting runs print chapter-level progress while they work. For each chapter,
the command reports the chapter index and artifact base name, whether formatting
was reused or regenerated, Sarvam attempt counts, retry sleeps, and the final
formatted paragraph count. R2-backed runs also report source download
completion, destination prefix availability, and byte counts during artifact
uploads. These messages are intended for normal operator runs and never include
API keys, request bodies, or full chapter text.

Every successful content-preparation run writes JSON and Markdown audit reports
under the generated subject tree:

```text
run_reports/
  CAT020_SUB129_spand-rahasya_run_<timestamp>.json
  CAT020_SUB129_spand-rahasya_run_<timestamp>.md
```

The JSON report is the tooling source of truth. The Markdown report is the
operator-readable view. Reports summarize run identity, job configuration,
copy/extraction and validation status, chapter counts, formatting outcomes,
Sarvam response token usage, retry candidates based only on
`formatting.status == "failed"`, and rate-limit/throttle evidence. Reports
intentionally exclude secrets, API keys, request bodies, and full chapter text.
For R2 destinations, the reports are uploaded with the rest of the subject
artifacts under the configured subject prefix.

The sample job `jobs/002_spand_rahasya.formatting-disabled.local.json` includes
an explicit disabled formatting block:

```json
{
  "formatting": {
    "enabled": false
  }
}
```

This sample is safe for normal local runs and does not require Sarvam
credentials. Use it when you want to verify the schema `1.3.0` formatting shape
without making API calls.

## Storage Configuration

The conversion job supports `local` and `r2` source/destination storage
backends. Existing jobs that omit `backend` are treated as local jobs.

Sample jobs are split by backend:

```text
jobs/001_aacharan_shaastra.local.json
jobs/001_aacharan_shaastra.r2-output.json
jobs/002_spand_rahasya.formatting-disabled.local.json
jobs/002_spand_rahasya.local.json
jobs/002_spand_rahasya.r2-output.json
```

Use `.local.json` for local source and local output. Use `.r2-output.json` for
local source and R2 artifact output.

Local source and destination:

```json
{
  "source": {
    "backend": "local",
    "root_dir": "/Users/rajeev/Gurubodh_library/source_library",
    "relative_path": "129_spand_rahasya/unicode_fonts/ms_word/spand_rahasya.docx",
    "font_encoding": "unicode",
    "file_format": "docx"
  },
  "destination": {
    "backend": "local",
    "root_dir": "/Users/rajeev/Gurubodh_library/cms_library",
    "subject_dir": "129_spand_rahasya"
  }
}
```

Cloudflare R2 source and destination:

```json
{
  "source": {
    "backend": "r2",
    "bucket": "gurubodh-library-dev",
    "key": "source_library/129_spand_rahasya/unicode_fonts/ms_word/spand_rahasya.docx",
    "font_encoding": "unicode",
    "file_format": "docx"
  },
  "destination": {
    "backend": "r2",
    "bucket": "gurubodh-library-dev",
    "prefix": "cms_library",
    "subject_dir": "129_spand_rahasya",
    "url_base": null
  }
}
```

R2 uses object keys, not real folders. Prepared artifact keys preserve the local
layout under the destination prefix:

```text
cms_library/{subject_dir}/full_subject/
cms_library/{subject_dir}/chapters/msword/
cms_library/{subject_dir}/chapters/text_and_metadata/
```

R2 objects may remain private. Generated metadata stores bucket/key references
as canonical storage references and leaves URL fields as `null` unless
`url_base` is configured.

## Chapter Text Integrity

Each generated chapter metadata JSON file includes:

```json
"integrity": {
  "artifacts": {
    "text": {
      "algorithm": "sha256",
      "encoding": "UTF-8",
      "line_endings": "LF",
      "scope": "artifact-bytes",
      "value": "..."
    }
  }
}
```

The `value` is the SHA-256 hex digest of the exact UTF-8 bytes written to the
chapter `.txt` artifact in `chapters/text_and_metadata/`, including the final LF
newline. It does not describe the metadata JSON file itself.

Content ingestion can compare this value with a previously ingested chapter to
skip unchanged text artifacts, detect source text changes across local and
R2-backed jobs, and decide when future chunks, embeddings, or RAG indexes need
to be rebuilt.

For R2 destinations, the tool checks the destination subject prefix before
processing starts. If objects already exist and `--overwrite` is not supplied,
the job fails before doing DOCX conversion or chapter splitting. During upload,
the tool prints count-based progress for object checks and uploads.

## Cloudflare R2 Credentials

R2 jobs read credentials from environment variables:

```bash
export CLOUDFLARE_R2_ACCOUNT_ID=...
export CLOUDFLARE_R2_ACCESS_KEY_ID=...
export CLOUDFLARE_R2_SECRET_ACCESS_KEY=...
```

Do not commit these values to the repository.
