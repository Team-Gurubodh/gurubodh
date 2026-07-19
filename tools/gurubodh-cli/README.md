# Gurubodh CLI

Python utilities for preparing Gurubodh CMS-ready content from DOCX source files.

## Setup

Run these commands from the monorepo root:

```bash
cd tools/gurubodh-cli
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
gurubodh prep-subject --config jobs/002_spand_rahasya.local.json
```

## What These Commands Do

`cd tools/gurubodh-cli` moves into this Python tool project.

`python3.12 -m venv .venv` creates a local virtual environment named `.venv`.
The Gurubodh CLI package is standardized on Python `>=3.12,<3.13`.

`. .venv/bin/activate` activates the virtual environment so dependencies and console commands are isolated to this project.

`python -m pip install -e .` installs the package in editable mode. This exposes the `gurubodh` command while keeping it linked to the source files in this directory. It also installs semantic chunking dependencies (`numpy`, `transformers`, and `sentence-transformers`) for future paragraphing and RAG preparation work. The first semantic chunking run may download the configured embedding model into the local Hugging Face cache.

If this virtual environment was moved from the old content-preparation path,
generated wrappers such as `.venv/bin/pip` may still point to that old absolute
path. In that case, run `python -m pip install -e .` after activation, or run
`.venv/bin/python -m pip install -e .` without activation, to refresh the
editable install.

`gurubodh prep-subject --config jobs/002_spand_rahasya.local.json` runs a sample local content job.

Existing output is not archived. If the configured local output directory or R2
objects already exist, re-run with `--overwrite` when you intentionally want to
replace them:

```bash
gurubodh prep-subject --config jobs/002_spand_rahasya.local.json --overwrite
```

## Project Root Detection

The CLI detects this tool's root by finding both:

```text
config/conversion_job.schema.json
jobs/
```

If running from another directory, pass the root explicitly:

```bash
gurubodh prep-subject \
  --project-root /Users/rajeev/Applications/gurubodh/tools/gurubodh-cli \
  --config jobs/002_spand_rahasya.local.json
```

## Future Command Surface

Future content ingestion, metadata generation, and metadata ingestion workflows
are expected to be added to this Python package and exposed through the
`gurubodh` command structure instead of separate placeholder tool
directories.

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

## Semantic Chunking

Semantic chunking is integrated as an internal `gurubodh` module:

```python
from gurubodh.ml.semantic_chunking import SemanticChunkConfig, SemanticChunker

config = SemanticChunkConfig(
    threshold_percentile=82,
    min_chars=700,
    window_size=3,
)

chunker = SemanticChunker(config)
document = chunker.chunk_text(raw_text, source_name="chapter.txt")
```

The module is intentionally not called by the existing DOCX preparation
pipelines yet. Issue #130 integrates the package structure so modified Task 014
work can evaluate semantic chunking for paragraph display and later RAG chunk
generation.

For standalone local evaluation, run:

```bash
python -m gurubodh.ml.semantic_chunking.cli \
  --source-dir path/to/text-files \
  --output-dir path/to/semantic-chunks
```

Current behavior returns chunk text and sentence ranges. Future Task 014 work
should add exact character spans into canonical chapter text before storing
semantic chunking output as durable chapter metadata or CMS-ingestion artifacts.
