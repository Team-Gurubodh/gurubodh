# Prepare a subject

`gurubodh prep-subject` is the normal, canonical preparation workflow. It reads a job's declared pipeline, processes a Unicode or supported legacy-font DOCX source, performs required Gemini proofreading, and publishes a prepared release only after every chapter succeeds.

## Run a maintained job

After configuring `GEMINI_API_KEY` as described in [Environment setup](../environment-setup.md), run:

```bash
gurubodh prep-subject \
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.local.json
```

The job must declare `hi-IN` or `mr-IN`, `Devanagari`, and UTF-8 output. `subject_dir` is a safe POSIX-relative nested path ending in that language, such as `123_spand_rahasya/hi-IN`. The two supported locales use their own proofreading instructions but share the structured response contract.

## What is published

For `<subject-group>/<language>/`, preparation owns:

```text
chapters/text_and_metadata/
chapters/unmodified_source_text/
chapters/proofreading/
chapters/chapter_content_manifest.json
run_state/prep-subject/job-state.json
run_reports/prep-subject/
```

The versioned text in `chapters/text_and_metadata/` is the canonical proofread text. Metadata is calculated from that exact text. Extracted source snapshots, diffs, and proofreading provenance are supporting records—not chunking inputs. Details of ownership, derived outputs, and readiness are in [Artifact lifecycle](../concepts/artifact-lifecycle.md).

`prep-subject` requires a `proofreading` object and `GEMINI_API_KEY`. It fails before publication for missing credentials, invalid configuration, oversized input, invalid or blocked model responses, and exhausted retry attempts. It does not publish chapter DOCX files or a `full_subject/` artifact.

## Resume and replacement

When an individual chapter fails, the command completes independently processable chapters, marks the release incomplete, and writes JSON and Markdown reports. Resume a compatible checkpoint without repeating successful proofreads:

```bash
gurubodh prep-subject \
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.local.json \
  --resume
```

`--resume` and `--overwrite` are mutually exclusive. Resume requires the same source and output-affecting preparation, naming, metadata, and proofreading contract. Use `--overwrite` when those inputs change:

```bash
gurubodh prep-subject \
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.local.json \
  --overwrite
```

An overwrite replaces only preparation-owned paths after a complete candidate is staged. It invalidates same-locale semantic chunks and DOCX exports because they can no longer be bound to the new canonical manifest. `prep-subject` is a single-writer operation per destination: run one writer per subject and locale. Its local advisory lock and R2 advisory lease are guardrails, not reliable mutual exclusion; concurrent runs can duplicate Gemini calls and overwrite checkpoint/workspace artifacts.

For R2, checkpoints are append-only commits. Initial source snapshots upload once with the chapter plan state commit; each successful chapter uploads only its newly generated text, metadata, diff, and provenance artifacts before the state that marks that chapter successful. Failure state changes upload state only, and advisory heartbeats upload neither workspace artifacts nor state. The job-state JSON is uploaded last for each checkpoint event.

Every invocation writes JSON and Markdown audit reports with run metrics and prints the same concise summary. `gemini_generate_content_requests` counts actual request attempts (including retries and terminal failures, excluding checkpoint reuse and local waits). R2 jobs also record `r2_object_upload_requests`: checkpoint and canonical-publication upload attempts, excluding reads, lists, deletes, and audit-report uploads. Both metrics expose total, succeeded, and failed attempts. R2 audit reports additionally break uploads down by source snapshots, successful chapter artifacts, state commits, overwrite archives, and canonical publication; the terminal prints totals only.

## Source handling and migration

Unicode DOCX sources are read directly. Supported APS and Shri-Lipi sources are converted only in a transient workspace; canonical output is always UTF-8 Unicode text. See [Legacy DOCX conversion](../reference/legacy-docx-conversion.md).

Older Hindi artifacts directly below `cms_library/<subject-group>/` are legacy locations. The CLI does not move or delete them automatically. Regenerate and verify the language-qualified release, then deliberately archive or delete the legacy artifacts as an operator action.
