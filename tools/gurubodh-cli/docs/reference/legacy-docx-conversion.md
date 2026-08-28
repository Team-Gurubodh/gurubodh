# Legacy DOCX conversion

`prep-subject` converts DOCX source files into Gurubodh canonical artifacts. This reference explains how it chooses its two supported source-handling pipelines; for normal operation, start with [Prepare a subject](../workflows/prepare-a-subject.md).

## Source-handling pipelines

The job's top-level `pipeline` and `source.font_encoding` select one route:

- `unicode-docx-ingest` requires `source.font_encoding: unicode` and reads the DOCX directly.
- `legacy-docx-to-unicode` requires `source.font_encoding: aps`. It converts APS legacy Devanagari font runs to Unicode only in a transient workspace.

Canonical output is always UTF-8 Unicode text. Preparation does not publish a converted full-subject DOCX or chapter DOCX. It retains the extracted input as a source-text snapshot and publishes proofread canonical text only after the entire subject succeeds.

`prep-subject` reads the configured route and is the normal command. `unicode-ingest` and `legacy-convert` are deprecated strict aliases; use them only when their additional pipeline assertion is specifically needed.

## Configuration

Configured sources must be `.docx`. A preparation job declares source and destination, pipeline, supported source-font encoding, chapter split, naming, metadata defaults, locale, and a mandatory proofreading contract. Review [Job configurations](job-configurations.md) and the current job schema before editing a maintained job.

## Source-font safety boundary

The CLI accepts only centrally approved Unicode font families and APS font
families. It preflights the actual effective font used by each text run before
conversion, proofreading, checkpoint creation, or canonical publication. This
includes direct formatting, inherited paragraph and character styles, document
defaults, headers, footers, footnotes, endnotes, and comments.

`source.font_encoding` remains either `unicode` or `aps`; it cannot approve a
new font family. There is intentionally no job-level bypass. An unapproved
font, including every ShreeLipi/Sri-Lipi/Shree Dev variant, stops the run. Use
an approved Unicode or APS DOCX, or ask a maintainer to review a genuinely
Unicode source family for addition to the central allowlist.

For example:

```text
Unsupported source font family detected: "SHREE-DEV7-0708".
ShreeLipi/Sri-Lipi conversion is disabled because verified font-specific mappings are unavailable.
This document was not processed; no canonical artifacts were created or published.
```

```json
{
  "pipeline": "unicode-docx-ingest",
  "source": {
    "font_encoding": "unicode",
    "file_format": "docx"
  },
  "destination": {
    "subject_dir": "129_spand_rahasya/hi-IN"
  }
}
```

The `subject_dir` is language-qualified. Legacy artifacts in an unqualified subject root are not moved or removed automatically; regenerate to the new root and handle any old artifacts deliberately.

## Project-root resolution

Run jobs from `tools/gurubodh-cli`, or pass `--project-root` when elsewhere. The CLI otherwise uses `GURUBODH_CLI_ROOT` and then searches upward for both `config/jobs/prep_subject_job.schema.json` and `jobs/subjects/`. See [Getting started](../getting-started.md) for examples.
