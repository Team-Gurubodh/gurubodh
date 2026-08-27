# Gurubodh CLI

Gurubodh CLI prepares Gurubodh subject content from DOCX files and produces the artifacts used by the CMS, search, and human review workflows. It is designed for repeatable, auditable jobs—not for editing published content by hand.

## Start here

If you are new to the tool, use a maintained local job first. From the monorepo root:

```bash
make cli-venv
. tools/gurubodh-cli/.venv/bin/activate
make cli-install
cd tools/gurubodh-cli
export GEMINI_API_KEY=...
gurubodh prep-subject \
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.local.json
```

This prepares canonical, proofread chapter artifacts locally. It needs an environment-only Gemini API key. Do not add credentials to a job file, command history, image, or repository configuration. See [Environment setup](docs/environment-setup.md) for the runtime and variables, and [Getting started](docs/getting-started.md) before using `--overwrite`, R2, or an unfamiliar job.

## What you can do today

| Goal | Command | Guide |
| --- | --- | --- |
| Prepare canonical chapter artifacts from a DOCX source | `prep-subject` | [Prepare a subject](docs/workflows/prepare-a-subject.md) |
| Generate semantic chunks from prepared canonical text | `generate-chunks` | [Generate chunks](docs/workflows/generate-chunks.md) |
| Generate one reviewable DOCX per canonical chapter | `generate-docx` | [Generate DOCX exports](docs/workflows/generate-docx.md) |
| Experiment with a local DOCX without publishing canonical artifacts | `lab` | [Lab tools](docs/workflows/lab-tools.md) |
| Estimate BGE-M3 tokens (and optionally Sarvam prompt tokens) | `compare-tokenizers` | [Command reference](docs/reference/command-reference.md) |

The supported production flow is:

```text
source DOCX → prep-subject → canonical chapter artifacts
                              ├─ generate-chunks → semantic chunks
                              └─ generate-docx   → reviewable DOCX exports
```

`prep-subject` is the source of canonical content. A successful `prep-subject --overwrite` invalidates derived chunks and DOCX exports, so regenerate the outputs you need afterward.

## Choose the right guide

- New contributor or first local run: [Getting started](docs/getting-started.md)
- Runtime, credentials, model cache, or Docker setup: [Environment setup](docs/environment-setup.md)
- Normal content preparation: [Prepare a subject](docs/workflows/prepare-a-subject.md)
- Chunk generation and the pinned local model cache: [Generate chunks](docs/workflows/generate-chunks.md)
- Rebuildable chapter Word exports: [Generate DOCX exports](docs/workflows/generate-docx.md)
- Docker and Cloudflare R2 operations: [R2 production runs](docs/operations/r2-production-runs.md)
- Artifact ownership, invalidation, canonical-content, and audit records: [Artifact lifecycle](docs/concepts/artifact-lifecycle.md)
- Job files, storage backends, locales, and command options: [Reference](docs/reference/README.md)

## Safety essentials

- Start with a `.local.json` maintained job. R2 jobs and Docker are for operators who have read the production runbook.
- Treat `--overwrite` as a deliberate replacement operation. It is scoped to the invoking command's artifacts, but it is not an atomic, versioned R2 release.
- Never run two writers for the same subject and locale concurrently.
- Run `gurubodh <command> --help` for the exact installed command interface; job schemas under `config/jobs/` define the machine-validated configuration.

## Documentation map

The [CLI documentation index](docs/README.md) is the entry point for focused guides, operational runbooks, concepts, and reference material. Documentation describes current behavior; planned command names shown by `gurubodh --help` are not supported workflows.
