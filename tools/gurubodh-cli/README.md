# Gurubodh CLI

Python utilities for preparing Gurubodh CMS-ready content from DOCX source files.

## Setup

Run these commands from the monorepo root:

```bash
cd tools/gurubodh-cli
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
export GEMINI_API_KEY=...
gurubodh prep-subject --config jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.local.json
```

## Container Batch Runner

Docker is the supported runner for production R2-to-R2 batch jobs. Native Python
execution remains supported for development and debugging. The published CPU-only
image is `ghcr.io/team-gurubodh/gurubodh-cli`; use an immutable digest or a
`sha-<full-git-sha>` tag, never an unpinned mutable reference.

Build and perform local smoke checks from the monorepo root:

```bash
docker build --build-arg SOURCE_REVISION="$(git rev-parse HEAD)" \
  --build-arg IMAGE_VERSION=local \
  --build-arg IMAGE_CREATED="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t gurubodh-cli:local tools/gurubodh-cli
docker run --rm gurubodh-cli:local --help
docker run --rm --entrypoint node gurubodh-cli:local --version
```

The image supplies Python 3.12 and Node for the bundled APS converter, runs as
a non-root user, and contains no credentials, content artifacts, or BGE-M3
weights. Its entrypoint is `gurubodh`; `/work` is a temporary workspace and
`/var/cache/gurubodh/models` is the model-cache path.

### R2-to-R2 production runs

Export credentials in the calling shell or put them in a local, untracked
environment file. Never add them to a job JSON file, image, command history, or
repository configuration.

```bash
export CLOUDFLARE_R2_ACCOUNT_ID=...
export CLOUDFLARE_R2_ACCESS_KEY_ID=...
export CLOUDFLARE_R2_SECRET_ACCESS_KEY=...
docker volume create gurubodh-bge-m3-cache
```

Provision the pinned model snapshot once for each new or repaired cache volume.
This is a deliberate online bootstrap step; maintained chunk-generation jobs do
not populate or repair their model caches.

```bash
docker run --rm \
  --mount type=volume,src=gurubodh-bge-m3-cache,dst=/var/cache/gurubodh/models \
  --entrypoint hf \
  ghcr.io/team-gurubodh/gurubodh-cli:sha-<full-git-sha> \
  download BAAI/bge-m3 \
  1_Pooling/config.json \
  config.json \
  config_sentence_transformers.json \
  modules.json \
  pytorch_model.bin \
  sentence_bert_config.json \
  sentencepiece.bpe.model \
  special_tokens_map.json \
  tokenizer.json \
  tokenizer_config.json \
  --revision 5617a9f61b028005a4858fdac845db406aefb181 \
  --cache-dir /var/cache/gurubodh/models
```

Run a prep job whose source DOCX and artifact destination are both R2:

```bash
docker run --rm \
  --env PYTHONUNBUFFERED=1 \
  --env GEMINI_API_KEY \
  --env CLOUDFLARE_R2_ACCOUNT_ID \
  --env CLOUDFLARE_R2_ACCESS_KEY_ID \
  --env CLOUDFLARE_R2_SECRET_ACCESS_KEY \
  --mount type=volume,src=gurubodh-bge-m3-cache,dst=/var/cache/gurubodh/models \
  ghcr.io/team-gurubodh/gurubodh-cli:sha-<full-git-sha> \
  prep-subject --config jobs/subjects/sub039_aacharan_shastra/hi-IN/prep-subject.r2.json
```

Then run its R2-backed chunk-generation job with the same named volume.
Maintained `generate-chunks` jobs use `local_files_only: true`, so they require
the exact pinned BGE-M3 snapshot to be present and never perform a Hugging Face
lookup. The volume remains reusable across stopped and recreated containers.

```bash
docker run --rm \
  --env PYTHONUNBUFFERED=1 \
  --env HF_HUB_OFFLINE=1 \
  --env CLOUDFLARE_R2_ACCOUNT_ID \
  --env CLOUDFLARE_R2_ACCESS_KEY_ID \
  --env CLOUDFLARE_R2_SECRET_ACCESS_KEY \
  --mount type=volume,src=gurubodh-bge-m3-cache,dst=/var/cache/gurubodh/models \
  ghcr.io/team-gurubodh/gurubodh-cli:sha-<full-git-sha> \
  generate-chunks --config jobs/subjects/sub039_aacharan_shastra/hi-IN/generate-chunks.r2.json
```

Generate the independent human-readable Word export after preparation. This
command needs no model cache and makes no Gemini or other external-model calls:

```bash
docker run --rm \
  --env CLOUDFLARE_R2_ACCOUNT_ID \
  --env CLOUDFLARE_R2_ACCESS_KEY_ID \
  --env CLOUDFLARE_R2_SECRET_ACCESS_KEY \
  ghcr.io/team-gurubodh/gurubodh-cli:sha-<full-git-sha> \
  generate-docx --config jobs/subjects/sub123_spand_rahasya/hi-IN/generate-docx.r2.json
```

If you already have the `bge-m3` cache and wish to reuse the same with the docker container, then use the following commands, replacing `--mount type=volume` by  `--mount type=bind`, as shown in the examples below:

```bash
# Run the `prep-subject` command
docker run --rm \
  --env PYTHONUNBUFFERED=1 \
  --env GEMINI_API_KEY \
  --env CLOUDFLARE_R2_ACCOUNT_ID \
  --env CLOUDFLARE_R2_ACCESS_KEY_ID \
  --env CLOUDFLARE_R2_SECRET_ACCESS_KEY \
  ghcr.io/team-gurubodh/gurubodh-cli:sha-<full-git-sha> \
  prep-subject --config jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.r2.json --overwrite


# Run the `generate-chunks` command
docker run --rm \
  --env PYTHONUNBUFFERED=1 \
  --env HF_HUB_OFFLINE=1 \
  --env CLOUDFLARE_R2_ACCOUNT_ID \
  --env CLOUDFLARE_R2_ACCESS_KEY_ID \
  --env CLOUDFLARE_R2_SECRET_ACCESS_KEY \
  --mount type=bind,src="$HOME/.cache/huggingface/hub",dst=/var/cache/gurubodh/models \
  ghcr.io/team-gurubodh/gurubodh-cli:sha-<full-git-sha> \
  generate-chunks --config jobs/subjects/sub123_spand_rahasya/hi-IN/generate-chunks.r2.json --overwrite

# The `--env PYTHONUNBUFFERED=1` flag disables buffered `stdout` and `stderr`,
# so logs appear immediately in docker logs or your terminal
# instead of being delayed until a buffer fills or the process exits.
# It’s useful for long-running CLI jobs and debugging.
```

The CLI downloads R2 inputs to temporary container storage and uploads outputs
back to R2. Audit reports are published under the subject's
`run_reports/prep-subject/` or `run_reports/generate-chunks/` prefix and identify
the baked image source revision and provenance source. Do not bind-mount a
working checkout over `/opt/gurubodh-cli` in production, as that defeats this
audit identity.

Job configurations are baked into the immutable image. After changing a
maintained `generate-chunks` configuration, build and publish a new image and
use its new immutable tag or digest; an existing image retains its previous
configuration.

`--overwrite` replaces only the command-owned output paths described below; it
does not create an atomic or versioned R2 publication. Retry failed jobs after
checking the reported R2 state, and never run concurrent jobs that write to the
same subject. The named cache volume is reusable but may be removed with
`docker volume rm gurubodh-bge-m3-cache` when its downloaded model snapshots are
no longer needed; the next chunk job will download them again if network access
is allowed.

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

`gurubodh prep-subject --config jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.local.json`
runs a sample local content job.

Artifact ownership is command-scoped: `prep-subject`
owns `chapters/text_and_metadata/`, `chapters/unmodified_source_text/`,
`chapters/proofreading/`, and `chapters/chapter_content_manifest.json`;
`generate-chunks` owns only `chapters/semantic_chunks/`; `generate-docx` owns
only `chapters/msword/`. The legacy
`chapters/semantic_chunks_and_embeddings/` location is removed only by an
explicit `generate-chunks --overwrite` migration run. Each command owns its own
command-specific audit history. `--overwrite` replaces only the invoking command's owned paths, never
the complete subject root. A successful `prep-subject --overwrite` invalidates
semantic chunks because they may no longer match the prepared content; rerun
`gurubodh generate-chunks --config <generate-chunks-job>` before using RAG output.
`prep-subject` also owns operational state at
`run_state/prep-subject/job-state.json` and staged checkpoints at
`.work/prep-subject/{job-id}/`. Cross-prefix local/R2 replacement is not a
fully atomic release protocol.

`prep-subject` still accepts a DOCX source, but Unicode sources are read
directly and legacy-font conversion uses only a transient Unicode working
DOCX. It does not publish `full_subject/` or `chapters/msword/`. The latter is
reserved for the separate `generate-docx` command. After a successful
canonical overwrite, prep invalidates same-locale `chapters/msword/`, removes
same-locale legacy `full_subject/`, and records both outcomes in job state and
run reports. Failed or incomplete overwrites leave those paths untouched.

### Locale-scoped Hindi and Marathi preparation

The CLI initially supports exactly `hi-IN` (Hindi) and `mr-IN` (Marathi). A
prep-subject job must explicitly declare its locale, `source_script` as
`Devanagari`, and `output_text_encoding` as `UTF-8`. Hindi and Marathi use
separate, locale-specific Gemini proofreading instructions while retaining the
same structured response and edit categories.

Every prepared release is rooted at `<subject-group>/<language>`, including
canonical artifacts, semantic chunks, reports, checkpoints, and workspaces:

```text
cms_library/<subject-group>/hi-IN/
cms_library/<subject-group>/mr-IN/
```

`subject_dir` must be a safe POSIX-relative nested path, retain a subject
grouping, and end in the configured language. Absolute paths, empty segments,
`.`, `..`, and backslashes are rejected. `generate-chunks` source and
destination must use the same language-qualified `subject_dir`, and its
`naming.language` must match the prepared manifest.

```json
{
  "destination": {
    "backend": "local",
    "root_dir": "/path/to/cms_library",
    "subject_dir": "123_spand_rahasya/mr-IN"
  },
  "metadata_defaults": {
    "language": "mr-IN",
    "source_script": "Devanagari",
    "output_text_encoding": "UTF-8",
    "summary_chapter_markers": []
  }
}
```

The matching Marathi chunk job uses `123_spand_rahasya/mr-IN` for both
`source.subject_dir` and `destination.subject_dir`, and sets
`naming.language` to `mr-IN`. This is a template only: supply an approved
Marathi source DOCX and subject metadata before creating an executable job.

```json
{
  "schema_version": "1.1.0",
  "pipeline": "generate-chunks",
  "source": {
    "backend": "local",
    "root_dir": "/path/to/cms_library",
    "subject_dir": "123_spand_rahasya/mr-IN"
  },
  "destination": {
    "backend": "local",
    "root_dir": "/path/to/cms_library",
    "subject_dir": "123_spand_rahasya/mr-IN"
  },
  "naming": {
    "category_code": "CAT001",
    "subject_code": "SUB123",
    "title_slug": "spand-rahasya",
    "version": "01",
    "subversion": "01",
    "language": "mr-IN"
  }
}
```

Run the language-matched jobs in order:

```bash
gurubodh prep-subject --config <marathi-prep-subject-job>
gurubodh generate-chunks --config <marathi-generate-chunks-job>
```

Proofreading details, aggregate proofreading manifests, checkpoints, and
prep-subject reports record the selected language and instruction-template ID,
version, and hash. They never record the full prompt, source/corrected text,
or credentials.

#### Migrating existing Hindi artifacts

Existing Hindi artifacts directly under `cms_library/<subject-group>/` are
legacy locations. The CLI never moves or deletes them automatically. Regenerate
the subject with a maintained `hi-IN` prep job, verify its audit report and
canonical manifest, then regenerate chunks using the matching `hi-IN` job.
The first run to the new root does not overwrite the old root. Use
`--overwrite` only when intentionally replacing an already-existing release in
the same language root; it cannot modify the other language root.

An incomplete checkpoint at the old unqualified root cannot be resumed into
the new language root. Finish or preserve that old run deliberately, then start
a new `hi-IN` preparation job. Retain legacy local/R2 artifacts until the new
release has been verified; archival or deletion is an explicit operator action.

### Mandatory Gemini proofreading and canonical chapter artifacts

`prep-subject` requires a `proofreading` object in every job and always reads
the Gemini credential from `GEMINI_API_KEY`. Do not put the key in a job JSON
file or audit report. Proofreading is strict: missing credentials, oversized
input, malformed/safety-blocked responses, invalid configuration, or exhausted
transient retries fail the run before any local promotion or R2 publication.

```json
"proofreading": {
  "provider": "google-ai-studio",
  "model": "gemini-3.7-flash",
  "max_output_tokens": 8192,
  "max_input_characters": 30000,
  "max_retries": 3,
  "initial_retry_delay_seconds": 2,
  "max_retry_delay_seconds": 30,
  "min_request_interval_seconds": 6,
  "max_requests_per_minute": 8,
  "max_estimated_input_tokens_per_minute": 20000
}
```

For each successful chapter, the versioned `.txt` under
`chapters/text_and_metadata/` is the canonical proofread text and its matching
metadata JSON is computed entirely from that text. The exact extracted input
submitted to Gemini is retained only as
`chapters/unmodified_source_text/*_unmodified_source.txt`. The chapter also has
`*.proofread.diff.txt` and `*.proofread.json` under `chapters/proofreading/`.
The details JSON binds the unmodified and corrected artifacts with checksums,
content identities, request provenance, local diff summary, and Gemini edit
explanations without storing full text, prompts, keys, or raw responses.
`proofreading_manifest.json` remains aggregate operational provenance.

Proof-reading is deliberately sequential and applies a local request/token
budget. It retries transient rate-limit, timeout, network, and server failures
with capped exponential backoff and jitter. It does not retry invalid
credentials, malformed structured output, safety blocks, or oversized chapters.
The content manifest is written only after every chapter succeeds and lists
only proofread canonical text/metadata. Therefore `generate-chunks` consumes
proofread text automatically and ignores the unmodified/proofreading paths.

During preparation, the CLI reports source materialization and validation,
chapter detection and source-text snapshot extraction, each sequential Gemini
request, canonical text/metadata and proofreading completion, manifest
publication, and overwrite invalidation. These messages contain paths, counts,
and timing only; they never print chapter text or credentials and never claim
to write full-subject or chapter DOCX artifacts.

```bash
gurubodh prep-subject --config jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.local.json --overwrite
```

### Local lab proofreading

`gurubodh lab proofread` is an explicitly non-canonical, local-only workflow
for experimenting with one DOCX. It does not use a job JSON file and never
writes to `cms_library/`, changes the supplied source, or writes beside it.
Provide the source, a supported locale, and a non-canonical lab root explicitly:

```bash
gurubodh lab proofread \
  --source /path/to/Gurubodh_library/lab/proofread/source-files/some_name.docx \
  --locale hi-IN \
  --lab-root /path/to/Gurubodh_library/lab
```

Only `hi-IN` and `mr-IN` are supported. The command detects supported APS and
Shri-Lipi legacy fonts and converts them only in a temporary workspace under
the lab run; Unicode DOCX is read directly. It makes one structured Gemini
request, rejecting extracted text that exceeds the configured request limit
before sending a request. Credentials remain environment-only via
`GEMINI_API_KEY`.

Every invocation creates a distinct, readable ID such as
`20260827-012049-690a55` below `<lab-root>/proofread/runs/<run-id>/`.
`output/` contains `<source-stem>_proofread.docx`,
`<source-stem>_proofread.txt`, and an operator README linking to the main
output and review artifacts. The DOCX uses Heading 2 for paragraphs that
exactly match `प्रबोधनातील स्मरणीय मुद्दे` or `स्वामी विश्वसंदेश`.
Extracted source text, readable diff, structured proofreading details, and a
human-readable report remain under `report/`, with `run_manifest.json` at the
run root. The manifest records source and generated-artifact SHA-256 values,
locale/template provenance, command/package provenance, and the outcome. Lab
artifacts are never canonical source text or CMS-ingestion input.

### Resuming an interrupted prep job

Each successful chapter is written and checksum-validated in the staged
workspace before `job-state.json` is updated. When an individual chapter fails,
the command finishes the remaining independently processable chapters, writes
an immutable JSON/Markdown run report, and exits non-zero with state
`incomplete`. Resume it without paying for already checkpointed chapters:

```bash
gurubodh prep-subject --config jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.local.json --resume
```

`--resume` and `--overwrite` are mutually exclusive. Resume requires the same
source DOCX and output-affecting pipeline, naming, metadata, and proofreading
contract; use `--overwrite` for a changed input. An overwrite archives the old
state and discards its workspace, but preserves existing canonical artifacts
and semantic chunks until the replacement is successfully published. Do not
run concurrent writers for a subject; a stale local lock or R2 lease can be
recovered safely with `--resume`.

The text-only prep checkpoint contract is version `2`. Incomplete checkpoints
created under the earlier six-artifact contract cannot resume; finish them
before upgrading or restart with `--overwrite`. A completed earlier release
remains valid input for `generate-chunks` and `generate-docx`
command, so it does not require another Gemini run merely because its metadata
still contains legacy DOCX/full-subject references. Running
`prep-subject --resume` against that old checkpoint requires `--overwrite` to
replace it.

`generate-chunks` now checks `job-state.json` and the canonical manifest before
it creates or deletes any chunk output. It refuses incomplete, publishing, or
legacy prepared trees until `prep-subject --resume` reaches `succeeded`.

`gurubodh generate-chunks` reads `chapters/chapter_content_manifest.json`
as the authoritative candidate set, validates its selected metadata/text
references before model initialization, and writes per-chapter semantic chunk
JSON files. It may use BGE-M3 contextual vectors to find boundaries but never
persists finalized chunk vectors:

```bash
export GURUBODH_MODEL_CACHE_DIR=~/.cache/huggingface/hub
gurubodh generate-chunks \
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/generate-chunks.local.json
```

### Pinned BGE-M3 model and cache workflow

Every maintained `generate-chunks` job, whether local or R2-backed, must set
`chunking.model_revision` to a full immutable Hugging Face commit SHA. The
selected BGE-M3 revision is
`5617a9f61b028005a4858fdac845db406aefb181`. Job validation rejects `null`,
branch names, tags, and abbreviated SHAs. This revision is recorded in each
chunk artifact, the semantic-chunks manifest, and the JSON/Markdown audit
reports.

Bootstrap or repair the cache explicitly, using the same cache directory the
job will use. Download only the files required by the SentenceTransformers
PyTorch loader; the repository also includes optional ONNX, ColBERT, sparse,
and image artifacts that normal chunk generation does not need. This is the
only step that should be online:

```bash
export GURUBODH_MODEL_CACHE_DIR="$HOME/.cache/huggingface/hub"
hf download BAAI/bge-m3 \
  1_Pooling/config.json \
  config.json \
  config_sentence_transformers.json \
  modules.json \
  pytorch_model.bin \
  sentence_bert_config.json \
  sentencepiece.bpe.model \
  special_tokens_map.json \
  tokenizer.json \
  tokenizer_config.json \
  --revision 5617a9f61b028005a4858fdac845db406aefb181 \
  --cache-dir "$GURUBODH_MODEL_CACHE_DIR"
```

Every maintained job already sets `chunking.local_files_only` to `true`. It
therefore requires the already-populated pinned snapshot, prevents an
unexpected network lookup, and fails clearly when the cache is empty or
incomplete. `HF_HUB_OFFLINE=1` is an additional Docker runtime safeguard after
bootstrap. Keep `local_files_only` false only for deliberate cache bootstrap or
repair tools, or for standalone experimental commands. The standalone
experimental command accepts an optional `--model-revision`; pass the same SHA
whenever those results need to be reproducible.

When run from outside `tools/gurubodh-cli`, pass `--project-root` just like
`prep-subject`:

```bash
gurubodh generate-chunks \
  --project-root /Users/rajeev/Applications/gurubodh/tools/gurubodh-cli \
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/generate-chunks.local.json
```

The output directory is scoped to:

```text
<subject-group>/<language>/chapters/semantic_chunks/
```

It contains one `*.chunks.json` file per processed chapter and a
`semantic_chunks_manifest.json`. Every artifact records the exact SHA-256
binding to its candidate manifest; the semantic manifest also records each
chunk artifact SHA-256 and a deterministic chunking configuration fingerprint.
The JSON/Markdown audit reports preserve the details of a particular run.
The command does not write chunk Markdown and does not update chapter metadata.
For `--overwrite`, only the semantic chunk output directory (and, if present,
the legacy combined-output directory), or the matching R2 prefixes, are
replaced.

### Generate chapter DOCX exports

`gurubodh generate-docx` reads the authoritative
`chapters/chapter_content_manifest.json`, requires the latest prep state to be
`succeeded` and bound to those exact manifest bytes, then validates every
manifest-listed metadata/text pair. It accepts current metadata schema `1.4.0`
and valid succeeded legacy schema `1.3.0`; legacy DOCX/full-subject fields are
ignored. It never reads unmodified-source text and never calls an external
model.

Run the maintained local job:

```bash
gurubodh generate-docx \
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/generate-docx.local.json
```

The command writes:

```text
<subject-group>/<language>/chapters/msword/
  <canonical-versioned-chapter-stem>.docx
  docx_manifest.json
```

Every document begins with the exact title
`<title_slug>: prabodhan <three-digit chapter number>`. Canonical blank-line
paragraphs become Word paragraphs and internal single LFs become Word line
breaks. Formatting contract `1.0.0` fixes one-inch margins, Noto Sans
Devanagari, 18-point Title and 11-point Normal styles, left-to-right direction,
1.15 line spacing, and paragraph spacing for Hindi and Marathi. Each package
and its exact canonical-text round trip are validated before publication.

`docx_manifest.json` is the readiness marker. It binds the exact source
manifest, canonical identities and text checksums, titles, formatting/title
contracts, and generated DOCX checksums. DOCX is a rebuildable human-readable
export; canonical proofread `.txt` remains authoritative and DOCX is never a
chunking candidate.

Without `--overwrite`, an existing `chapters/msword/` fails preflight. Local
overwrite stages and validates the complete replacement before swapping only
that directory. R2 overwrite removes the old readiness manifest first, uploads
validated DOCX objects, and publishes `docx_manifest.json` last. A partial R2
prefix without the manifest is not ready; rerun with `--overwrite`. The command
does not remove `full_subject/`, invalidate semantic chunks, or alter canonical
artifacts. A successful `prep-subject --overwrite` does invalidate the previous
DOCX set, so rerun `generate-docx` afterward when exports are needed.

## Audit Trail Reports

Each successful `prep-subject` run writes machine-readable JSON and
operator-readable Markdown audit reports under the generated subject artifact
tree:

```text
<subject-group>/<language>/run_reports/prep-subject/
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
cms_library/{subject_dir}/run_reports/prep-subject/
```

Audit reports intentionally exclude secrets, environment variable values, API
keys, request bodies, full source text, full chapter text, and DOCX contents.

`generate-chunks` follows the same audit report convention and writes JSON and
Markdown reports under `<subject-group>/<language>/run_reports/generate-chunks/`. Reports include generated
artifact references and aggregate counts, but exclude full source text and
embedding vectors.

`generate-docx` writes successful and failed JSON/Markdown reports under
`<subject-group>/<language>/run_reports/generate-docx/`. Reports include source
manifest identity, formatting/title contracts, per-chapter canonical identity,
generated title, output filename/checksum, and publication outcome. They exclude
canonical text, DOCX contents, source DOCX contents, secrets, and environment
values.

## Chapter Content Identity

Prepared chapter metadata contains a deterministic `content_identity` object.
`content_key` is a UUID v5 provenance key for normalized chapter text within a
category, subject, and language; it is not a stable editorial chapter ID. Text
edits produce a new key, while reordering unchanged text does not. The
normalization contract is NFC Unicode, LF line endings, no trailing spaces or
tabs per line, and no outer Unicode whitespace; internal whitespace and
punctuation remain unchanged. `chapters/chapter_content_manifest.json` records the current
subject output set, and chunk artifacts copy their source identity.

Artifacts created before this contract must be regenerated with
`gurubodh prep-subject --overwrite` before `gurubodh generate-chunks` can use
them. The existing exact artifact-byte checksum remains separate from the
normalized content checksum.

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
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.local.json
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
jobs/subjects/sub039_aacharan_shastra/hi-IN/prep-subject.local.json
jobs/subjects/sub039_aacharan_shastra/hi-IN/prep-subject.r2-output.json
jobs/subjects/sub039_aacharan_shastra/hi-IN/generate-chunks.local.json
jobs/subjects/sub039_aacharan_shastra/hi-IN/generate-chunks.r2-output.json
jobs/subjects/sub039_aacharan_shastra/hi-IN/generate-chunks.r2.json
jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.local.json
jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.r2-output.json
jobs/subjects/sub123_spand_rahasya/hi-IN/generate-chunks.local.json
jobs/subjects/sub123_spand_rahasya/hi-IN/generate-chunks.r2-output.json
jobs/subjects/sub123_spand_rahasya/hi-IN/generate-chunks.r2.json
jobs/subjects/sub123_spand_rahasya/hi-IN/generate-docx.local.json
jobs/subjects/sub123_spand_rahasya/hi-IN/generate-docx.r2-output.json
jobs/subjects/sub123_spand_rahasya/hi-IN/generate-docx.r2.json
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
    "subject_dir": "129_spand_rahasya/hi-IN"
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
    "subject_dir": "129_spand_rahasya/hi-IN",
    "url_base": null
  }
}
```

R2 uses object keys, not real folders. Prepared artifact keys preserve the local
layout under the destination prefix:

```text
cms_library/{subject_dir}/chapters/text_and_metadata/
cms_library/{subject_dir}/chapters/unmodified_source_text/
cms_library/{subject_dir}/chapters/proofreading/
cms_library/{subject_dir}/chapters/chapter_content_manifest.json
```

R2 objects may remain private. Generated metadata stores bucket/key references
as canonical storage references and leaves URL fields as `null` unless
`url_base` is configured.

`generate-chunks` R2 jobs read and write prepared subject artifact trees using
the same `cms_library/{subject_dir}/` convention. Chunk artifacts are uploaded
under:

```text
cms_library/{subject_dir}/chapters/semantic_chunks/
```

`generate-docx` uses the same subject-artifact backend model and publishes its
ready export set plus append-only audits under:

```text
cms_library/{subject_dir}/chapters/msword/
cms_library/{subject_dir}/run_reports/generate-docx/
```

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

For R2 destinations, existing prep-owned output or a legacy `full_subject/`
prefix requires `--overwrite`. Replacement and cleanup happen only after the
complete candidate is staged; an incomplete run preserves published canonical
content and derived outputs. Successful replacement removes stale prep-owned
objects, invalidates same-locale DOCX and semantic outputs, removes legacy
`full_subject/`, and preserves both commands' report history and unrelated
objects.

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

The config-driven `generate-chunks` pipeline uses this module after it has
validated the prepared candidate manifest. The standalone interface remains
useful for local paragraphing experiments; it does not publish preparation
artifacts.

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
checksums, per-chunk `estimated_token_count`, and a source/chunks
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
