# Gurubodh CLI

Python utilities for preparing Gurubodh CMS-ready content from DOCX source files.

## Setup

Run these commands from the monorepo root:

```bash
cd tools/gurubodh-cli
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
gurubodh prep-subject --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
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

`gurubodh prep-subject --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json`
runs a sample local content job.

Existing output is not archived. If the configured local output directory or R2
objects already exist, re-run with `--overwrite` when you intentionally want to
replace them:

```bash
gurubodh prep-subject --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json --overwrite
```

## Audit Trail Reports

Each successful `prep-subject` run writes machine-readable JSON and
operator-readable Markdown audit reports under the generated subject artifact
tree:

```text
<subject>/run_reports/
```

The JSON report is the source of truth for tooling. The Markdown report is a
human-readable summary for reviewing what happened during the run. Reports
include run identity, the resolved job config path, pipeline, source and
destination backends, overwrite mode, a safe configuration snapshot, chapter
artifact summaries, text artifact SHA-256 values copied from chapter metadata,
publish status, and final operator notes.

For R2-backed destinations, audit reports are uploaded with the rest of the
subject artifact tree:

```text
cms_library/{subject_dir}/run_reports/
```

Audit reports intentionally exclude secrets, environment variable values, API
keys, request bodies, full source text, full chapter text, and DOCX contents.

Future Gurubodh CLI commands that create, transform, publish, ingest, delete, or
materially modify content artifacts should use the same JSON/Markdown audit
report convention, or explicitly document why an audit trail is not required.
Future command issues should include an audit-trail checklist:

```markdown
- [ ] Audit trail considered:
  - [ ] command writes standard JSON/Markdown audit reports; or
  - [ ] issue explains why no audit report is needed.
```

## Project Root Detection

The CLI detects this tool's root by finding both:

```text
config/jobs/prep_subject_job.schema.json
jobs/subjects/
```

If running from another directory, pass the root explicitly:

```bash
gurubodh prep-subject \
  --project-root /Users/rajeev/Applications/gurubodh/tools/gurubodh-cli \
  --config jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
```

## Future Command Surface

Future content ingestion, metadata generation, and metadata ingestion workflows
are expected to be added to this Python package and exposed through the
`gurubodh` command structure instead of separate placeholder tool
directories.

## Storage Configuration

The prep-subject job supports `local` and `r2` source/destination storage
backends. Existing jobs that omit `backend` are treated as local jobs.

Sample jobs are grouped by subject and split by backend:

```text
jobs/subjects/sub039_aacharan_shastra/prep-subject.local.json
jobs/subjects/sub039_aacharan_shastra/prep-subject.r2-output.json
jobs/subjects/sub123_spand_rahasya/prep-subject.local.json
jobs/subjects/sub123_spand_rahasya/prep-subject.r2-output.json
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

## Summary Chapter Tags

Chapter metadata automatically adds summary tags when generated chapter text
contains a configured summary marker. Matching chapters include:

```json
"content": {
  "automated_tags": ["summary_chapter", "उपसंहार"]
}
```

Jobs configure the marker terms under `metadata_defaults`:

```json
"metadata_defaults": {
  "language": "hi-IN",
  "source_script": "Devanagari",
  "output_text_encoding": "UTF-8",
  "summary_chapter_markers": [
    "उपसंहार",
    "उपसंहारात्मक",
    "उपसंभारात्मक",
    "उपसंभारात्त्मक",
    "उपसंभार"
  ]
}
```

If `summary_chapter_markers` is omitted, the CLI does not run summary chapter
detection for that job.

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
    threshold_percentile=78,
    min_chars=550,
    window_size=3,
)

chunker = SemanticChunker(config)
document = chunker.chunk_text(raw_text, source_name="chapter.txt")
```

The module is intentionally not called by the existing DOCX preparation
pipelines yet. Issue #130 integrates the package structure so modified Task 014
work can evaluate semantic chunking for paragraph display and later RAG chunk
generation.

Before running standalone semantic chunking, set the Gurubodh model cache
environment variable. The command fails clearly if this variable is omitted:

```bash
export GURUBODH_MODEL_CACHE_DIR=~/.cache/huggingface/hub
```

For standalone local evaluation, run:

```bash
gurubodh generate-chunks \
  --source-dir /Users/rajeev/Gurubodh_library/cms_library/39_aacharan_shaastra/chapters/text_and_metadata \
  --output-dir /Users/rajeev/Gurubodh_library/cms_library/39_aacharan_shaastra/chapters \
  --model-name BAAI/bge-m3 \
  --threshold-percentile 78 \
  --min-chars 550 \
  --window-size 3 \
  --batch-size 16 \
  --device cpu
```

Outputs are written under `semantic_chunks_bge_m3/` inside the requested output
directory. Existing output causes the command to fail unless `--overwrite` is
supplied. Use `--chapter` or `--chapters` to process a smaller evaluation set.
During processing, the command prints line-based progress with the resolved
source/output paths, model cache, number of chapter files, per-chapter read,
segmentation, validation, write steps, and final file/chunk totals.

The standalone output includes provider/model metadata, explicit chunking
parameters, zero-based end-exclusive Python character spans, per-chunk SHA-256
checksums, per-chunk `estimated_embedding_token_count`, and a source/chunks
checksum round trip. The token estimate is counted with the BGE-M3 tokenizer
without special tokens and represents the BGE-M3 input token size if the chunk
were embedded as one standalone input; it is not an API billing metric for the
local chunking workflow. The checksum round trip removes whitespace using
Python `str.isspace()` before hashing so formatting differences in chapter
whitespace do not affect content validation.

## Tokenizer Comparison

Use `compare-tokenizers` to estimate how prepared chapter text maps to local
BGE-M3 embedding tokens and, when explicitly approved, Sarvam chat prompt
tokens:

```bash
gurubodh compare-tokenizers \
  --source-file /Users/rajeev/Gurubodh_library/cms_library/39_aacharan_shaastra/chapters/text_and_metadata/001.txt
```

For a directory of prepared chapter text files:

```bash
gurubodh compare-tokenizers \
  --source-dir /Users/rajeev/Gurubodh_library/cms_library/39_aacharan_shaastra/chapters/text_and_metadata \
  --chapter 001 \
  --chapters 002 003.txt \
  --model-name BAAI/bge-m3
```

The command removes all Unicode whitespace before token counting, while keeping
the original whitespace-delimited word count for ratio reporting. Progress is
printed to stderr so text and JSON results on stdout can still be redirected to
a file.

Sarvam comparison sends source text to an external API and is disabled by
default. To enable it, set the API key and pass both explicit flags:

```bash
export SARVAM_API_KEY=...

gurubodh compare-tokenizers \
  --source-dir /Users/rajeev/Gurubodh_library/cms_library/39_aacharan_shaastra/chapters/text_and_metadata \
  --include-sarvam \
  --approve-external-api \
  --sarvam-model sarvam-105b
```

Machine-readable output is available with `--format json`.
