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

## Storage Configuration

The conversion job supports `local` and `r2` source/destination storage
backends. Existing jobs that omit `backend` are treated as local jobs.

Sample jobs are split by backend:

```text
jobs/001_aacharan_shaastra.local.json
jobs/001_aacharan_shaastra.r2-output.json
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
