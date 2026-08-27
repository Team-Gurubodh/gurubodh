# Prepare a subject

`gurubodh prep-subject` is the normal, canonical preparation workflow. It reads a job's declared pipeline, processes a Unicode or supported legacy-font DOCX source, performs required Gemini proofreading, and publishes a prepared release only after every chapter succeeds.

## Run a maintained job

```bash
export GEMINI_API_KEY=...
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

An overwrite replaces only preparation-owned paths after a complete candidate is staged. It invalidates same-locale semantic chunks and DOCX exports because they can no longer be bound to the new canonical manifest. It is not a concurrent-writer or atomic-publication protocol; run one writer per subject and locale.

## Source handling and migration

Unicode DOCX sources are read directly. Supported APS and Shri-Lipi sources are converted only in a transient workspace; canonical output is always UTF-8 Unicode text. See [Legacy DOCX conversion](../README-LEGACY-TO-UNICODE-CONVERSION-DOCX.md).

Older Hindi artifacts directly below `cms_library/<subject-group>/` are legacy locations. The CLI does not move or delete them automatically. Regenerate and verify the language-qualified release, then deliberately archive or delete the legacy artifacts as an operator action.
