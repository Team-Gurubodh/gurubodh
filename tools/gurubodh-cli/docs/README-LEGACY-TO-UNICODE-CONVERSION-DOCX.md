# DOCX To CMS Conversion Workflow

This project converts Microsoft Word `.docx` files into Gurubodh CMS-ready
outputs. It supports two pipelines:

- `legacy-docx-to-unicode`: convert supported legacy Devanagari font encodings
  such as APS into Unicode output.
- `unicode-docx-ingest`: ingest Unicode Devanagari DOCX files without font
  conversion, while still extracting text, splitting chapters, and writing
  metadata.

The Word document is the source of truth. The preferred workflow is config
based, so repeated runs produce the same directory layout, filenames,
full-subject output, chapter output, and metadata.

## Day-One Commands

From the project root, use the Python package CLI:

```bash
python3 -m gurubodh prep-subject --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
```

`prep-subject` is the normal command for job execution. It reads the job config,
inspects the top-level `pipeline` field, and dispatches to the correct
pipeline.

You can also call a strict pipeline command:

```bash
python3 -m gurubodh unicode-ingest --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
python3 -m gurubodh legacy-convert --config jobs/subjects/sub039_aacharan_shastra/prep-subject.local.json
```

Strict commands are useful when you want the command itself to assert the
expected pipeline. For example, `unicode-ingest` rejects a legacy APS job before
writing output.

## Which Command Should I Use?

Use `prep-subject` for normal operations:

```bash
python3 -m gurubodh prep-subject --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
python3 -m gurubodh prep-subject --config jobs/subjects/sub039_aacharan_shastra/prep-subject.local.json
```

Use `unicode-ingest` when the source DOCX is already Unicode:

```bash
python3 -m gurubodh unicode-ingest --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
```

Use `legacy-convert` when the source DOCX contains a supported legacy font
encoding:

```bash
python3 -m gurubodh legacy-convert --config jobs/subjects/sub039_aacharan_shastra/prep-subject.local.json
```

## Project Root Detection

The CLI must know the project root so it can find schemas, jobs, and the local
legacy converter files.

When running from a source checkout without installing the package, run commands
from the project root:

```bash
python3 -m gurubodh prep-subject --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
```

If you run from another directory before installing the package, Python also
needs the project on its import path:

```bash
PYTHONPATH=/path/to/gurubodh/tools/gurubodh-cli \
  python3 -m gurubodh prep-subject \
  --project-root /path/to/gurubodh/tools/gurubodh-cli \
  --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
```

After package installation, `python3 -m gurubodh ...` and the optional
`gurubodh ...` console command can be used from any directory.

Root detection order:

1. `--project-root`, if supplied.
2. `GURUBODH_CLI_ROOT`, if set.
3. Walk upward from the current directory until both are found:
   - `config/jobs/prep_subject_job.schema.json`
   - `jobs/subjects/`

Examples:

```bash
python3 -m gurubodh prep-subject --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
python3 -m gurubodh prep-subject --project-root /path/to/gurubodh/tools/gurubodh-cli --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
GURUBODH_CLI_ROOT=/path/to/gurubodh/tools/gurubodh-cli python3 -m gurubodh prep-subject --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
```

Relative config paths are resolved from the current directory when possible,
then from the detected project root.

## Job Config Files

Job configs live in:

```text
jobs/subjects/<subject>/
```

The current schemas live in:

```text
config/jobs/prep_subject_job.schema.json
config/artifacts/chapter_metadata.schema.json
```

Each job config declares:

- `schema_version`
- `pipeline`
- source root and relative `.docx` path
- source font encoding and source file format
- destination root and subject directory
- naming fields for category, subject, title slug, version, and subversion
- chapter split behavior
- metadata defaults

Configured source files must be `.docx`.

Supported `source.font_encoding` values are:

- `aps`: convert APS-family legacy font runs to Unicode.
- `shreelipi`: convert ShreeLipi-family legacy font runs to Unicode.
- `unicode`: copy the source DOCX unchanged, extract Unicode text, and produce
  the same full-subject and chapter outputs without font conversion.

The top-level `pipeline` field selects the processing route:

- `legacy-docx-to-unicode`: requires `source.font_encoding` to be `aps` or
  `shreelipi`.
- `unicode-docx-ingest`: requires `source.font_encoding` to be `unicode`.

## Config Examples

Unicode source:

```json
{
  "schema_version": "1.2.0",
  "pipeline": "unicode-docx-ingest",
  "source": {
    "root_dir": "/Users/rajeev/Gurubodh_library/source_library",
    "relative_path": "129_spand_rahasya/unicode_fonts/ms_word/spand_rahasya.docx",
    "font_encoding": "unicode",
    "file_format": "docx"
  },
  "destination": {
    "root_dir": "/Users/rajeev/Gurubodh_library/cms_library",
    "subject_dir": "129_spand_rahasya"
  },
  "chapter_split": {
    "enabled": true,
    "pattern_type": "regex",
    "pattern": "प्रबोधन.*?जनवरी.*?२०२६"
  }
}
```

Legacy APS source:

```json
{
  "schema_version": "1.2.0",
  "pipeline": "legacy-docx-to-unicode",
  "source": {
    "root_dir": "/Users/rajeev/Gurubodh_library/source_library",
    "relative_path": "39_aacharan_shaastra/aps_fonts/ms_word/aacharanshstra.docx",
    "font_encoding": "aps",
    "file_format": "docx"
  }
}
```

The examples above are shortened. Real job files also include `destination`,
`naming`, `chapter_split`, and `metadata_defaults`.

## Output Layout

The config resolves the input from:

```text
source.root_dir + source.relative_path
```

The config writes output under:

```text
destination.root_dir/destination.subject_dir/
  chapters/
    msword/
    text_and_metadata/
  full_subject/
```

If the subject output directory already exists, the CLI archives it under:

```text
destination.root_dir/archive/
```

and then regenerates the subject output from the current job.

Full-subject files are named from:

```text
category_code
subject_code
title_slug
full
vversion.subversion
```

Example:

```text
full_subject/
  CAT020_SUB129_spand-rahasya_full_v01.01.docx
  CAT020_SUB129_spand-rahasya_full_v01.01.txt
```

Chapter files use chapter numbers starting at `001`:

```text
chapters/
  msword/
    CAT020_SUB129_spand-rahasya_001_v01.01.docx
  text_and_metadata/
    CAT020_SUB129_spand-rahasya_001_v01.01.txt
    CAT020_SUB129_spand-rahasya_001_v01.01.json
```

## Metadata

Chapter metadata uses schema `1.2.0` and records processing details separately
from conversion facts.

When a job is run through the dispatcher:

```bash
python3 -m gurubodh prep-subject --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
```

metadata records:

```json
"processing": {
  "pipeline": "unicode-docx-ingest",
  "entry_point": "python3 -m gurubodh prep-subject"
}
```

When a job is run through the strict Unicode command:

```bash
python3 -m gurubodh unicode-ingest --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
```

metadata records:

```json
"processing": {
  "pipeline": "unicode-docx-ingest",
  "entry_point": "python3 -m gurubodh unicode-ingest"
}
```

The `pipeline` is the actual processing route. The `entry_point` is the command
route used to invoke it.

Conversion details look like:

```json
"conversion": {
  "source_font_encoding": "unicode",
  "source_file_format": "docx",
  "output_text_encoding": "UTF-8",
  "converter_counts": {}
}
```

Legacy jobs populate `converter_counts`, for example:

```json
"converter_counts": {
  "aps": 105
}
```

## Chapter Splitting

Chapter splitting is configured in JSON. Use `literal` when the marker is
stable:

```json
"chapter_split": {
  "enabled": true,
  "pattern_type": "literal",
  "pattern": "प्रबोधन क्र"
}
```

Use `regex` when the marker varies:

```json
"chapter_split": {
  "enabled": true,
  "pattern_type": "regex",
  "pattern": "प्रबोधन\\s+क्र\\.?\\s*[०-९0-9]+"
}
```

Regex patterns are Python regular expressions compiled when the config is
loaded. Do not wrap them in JavaScript-style `/.../u` delimiters.

## Dependencies

Required for all jobs:

```text
python3
```

Required only for legacy font conversion:

```text
node
```

Unicode DOCX jobs do not require `node`.

The legacy conversion path calls:

```text
scripts/legacy_font_convert.js
```

using local converter files in:

```text
scripts/vendor/
```

No website is contacted at runtime.

## Troubleshooting

If the CLI cannot find the project root, run from inside the project directory
or pass `--project-root`.

If a strict pipeline command rejects a config, check that the command and
config agree:

```text
unicode-ingest       -> pipeline unicode-docx-ingest, source font unicode
legacy-convert       -> pipeline legacy-docx-to-unicode, source font aps/shreelipi
```

If a regex chapter split produces no chapters, verify the pattern is Python
regex syntax and that the marker text appears in the DOCX body text.
