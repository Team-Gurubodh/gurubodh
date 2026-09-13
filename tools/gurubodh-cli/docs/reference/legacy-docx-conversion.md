# Legacy DOCX conversion

`prep-subject` converts DOCX source files into Gurubodh canonical artifacts. This reference explains how it chooses its two supported source-handling pipelines; for normal operation, start with [Prepare a subject](../workflows/prepare-a-subject.md).

## Source-handling pipelines

The job's top-level `pipeline` and `source.font_encoding` select one route:

- `unicode-docx-ingest` requires `source.font_encoding: unicode`, verifies that
  every text-bearing run resolves only to centrally approved Unicode font
  families, and then reads the DOCX directly.
- `legacy-docx-to-unicode` requires `source.font_encoding: aps`. It converts APS legacy Devanagari font runs to Unicode only in a transient workspace.

Canonical output is always UTF-8 Unicode text. Preparation does not publish a converted full-subject DOCX or chapter DOCX. It retains the extracted input as a source-text snapshot and publishes proofread canonical text only after the entire subject succeeds.

`prep-subject` selects the conversion or Unicode ingest pipeline from the chosen manifest edition. Use the invocation in [Prepare a subject](../workflows/prepare-a-subject.md); the former strict aliases are retired.

## Configuration

Configured sources must be `.docx`. A preparation job declares source and destination, pipeline, supported source-font encoding, chapter split, naming, metadata defaults, locale, and a mandatory proofreading contract. Review the current job schema before editing a maintained job.

## Source-font safety boundary

The CLI accepts only centrally approved Unicode font families and APS font
families. It preflights the actual effective font used by each text-bearing run
before extraction, conversion, proofreading, checkpoint creation or reuse, or
canonical publication, including resumed jobs. This includes direct
formatting, inherited paragraph and character styles, document defaults, theme
fonts, headers, footers, footnotes, endnotes, and comments.

The selected pipeline determines the allowed subset. `unicode-docx-ingest` is
strictly Unicode-only: every resolved effective family must appear in
`approved_unicode_font_families`. APS, unsupported legacy, and otherwise
unapproved families reject the whole document; a text-bearing run with no
resolvable effective font is also rejected. The error names the DOCX part and
run location. The CLI does not switch pipelines or convert APS text when the
manifest selects Unicode ingestion. `legacy-docx-to-unicode` continues to
convert supported APS runs while preserving approved Unicode runs, and
`lab proofread` continues to detect and convert supported APS automatically.

`source.font_encoding` remains either `unicode` or `aps`; it cannot approve a
new font family. There is intentionally no job-level bypass. An unapproved
font, including every ShreeLipi/Sri-Lipi/Shree Dev variant, stops the run. Use
an approved Unicode or APS DOCX, or ask a maintainer to review a genuinely
Unicode source family for addition to the central allowlist.

Approvals for both `prep-subject` and `lab proofread` live in
[`config/policies/source-fonts.json`](../../config/policies/source-fonts.json).
To approve another Unicode family, add its complete name to
`approved_unicode_font_families`, retaining `schema_version: "1.0.0"`, then
test and rebuild/reinstall the CLI package or container. No Python change is
needed. The bundled policy is shared across all subjects and languages;
subject manifests, execution profiles, project catalogs, and the working
directory cannot override it.

Family matching ignores case and collapses whitespace, but requires the whole
name: approving `Mangal` does not approve `Mangal Extra`. The
[`source-fonts.schema.json`](../../config/policies/source-fonts.schema.json)
schema rejects unknown fields, empty lists, blank names, duplicates, and
wildcards. Runtime validation also rejects duplicates after normalization and
entries matching known APS or unsupported ShreeLipi classifications. Legacy
detection and conversion rules remain unchanged.

Each source preflight loads and validates the policy. Missing, unreadable, or
malformed policy data stops processing with a configuration error; there is no
fallback allowlist. Reinstall from a complete package or checkout if a bundled
policy or schema is missing or damaged.

For example, Unicode ingestion can fail with:

```text
Unicode-only source-font requirement failed: font family "APS-DV-Prakash" at
DOCX part "word/document.xml", paragraph 2, run 1 is not an approved Unicode
font family.
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
