# Gurubodh CLI

Gurubodh CLI prepares Gurubodh subject content from DOCX files and produces the artifacts used by the CMS, search, and human review workflows. It is designed for repeatable, auditable jobs—not for editing published content by hand.

## Start here

Start with [Getting started](docs/getting-started.md): install the CLI, place
supplied source material, inspect configuration, prepare locally, derive matching
chunks/DOCX, and verify readiness. [Environment setup](docs/environment-setup.md)
owns runtime, credentials, library roots, and cache prerequisites.

## What you can do today

| Goal | Command | Guide |
| --- | --- | --- |
| Prepare canonical chapter artifacts from a DOCX source | `prep-subject` | [Prepare a subject](docs/workflows/prepare-a-subject.md) |
| Check the Node prerequisite and bundled APS converter | `legacy-font check` | [Environment setup](docs/environment-setup.md#local-development-runtime) |
| Generate semantic chunks from prepared canonical text | `generate-chunks` | [Generate chunks](docs/workflows/generate-chunks.md) |
| Generate one reviewable DOCX per canonical chapter | `generate-docx` | [Generate DOCX exports](docs/workflows/generate-docx.md) |
| Prepare or verify the pinned BGE-M3 runtime cache, or check upstream revisions | `models prepare`, `models verify`, `models check-updates` | [Manage the model](docs/workflows/manage-model-cache.md) |
| Validate and inspect a composed job | `config resolve` | [Command reference](docs/reference/command-reference.md#config-resolve) |
| Experiment with a local DOCX without publishing canonical artifacts | `lab` | [Local tool recipes](docs/workflows/local-tools.md) |
| Estimate BGE-M3 tokens (and optionally Sarvam prompt tokens) | `compare-tokenizers` | [Local tool recipes](docs/workflows/local-tools.md) |

The supported production flow is:

```text
source DOCX → prep-subject → canonical chapter artifacts
                              ├─ generate-chunks → semantic chunks
                              └─ generate-docx   → reviewable DOCX exports
```

`prep-subject` is the source of canonical content. A successful overwrite-authorized
job invalidates derived chunks and DOCX exports, including when an interrupted
`--overwrite` job completes through `--resume`; regenerate the outputs you need
afterward.

## Choose the right guide

- New contributor or first local run: [Getting started](docs/getting-started.md)
- Runtime, credentials, model cache, or Docker setup: [Environment setup](docs/environment-setup.md)
- Add a subject or language edition: [Subject setup](docs/workflows/add-a-subject.md)
- Failed/incomplete outcomes and reruns: [Recovery decisions](docs/operations/recovery.md)
- Normal content preparation: [Prepare a subject](docs/workflows/prepare-a-subject.md)
- Chunk generation and the pinned local model cache: [Generate chunks](docs/workflows/generate-chunks.md)
- Rebuildable chapter Word exports: [Generate DOCX exports](docs/workflows/generate-docx.md)
- Docker and Cloudflare R2 operations: [Docker and R2 operations](docs/operations/r2-production-runs.md)
- Artifact ownership, invalidation, canonical-content, and audit records: [Artifact lifecycle](docs/concepts/artifact-lifecycle.md)
- Composed configuration, storage routing, locales, and command options: [Reference](docs/reference/README.md)

## Safety essentials

- Start with a maintained subject and the `local` storage profile. R2 jobs and Docker are for operators who have read the production runbook.
- Treat `--overwrite` as a deliberate replacement operation. It is scoped to the invoking command's artifacts, but it is not an atomic, versioned R2 release.
- `prep-subject` is a single-writer operation per destination. The local advisory lock and R2 advisory lease are guardrails only, not reliable distributed mutual exclusion; concurrent runs can duplicate Gemini calls and overwrite checkpoint/workspace artifacts.
- Run `gurubodh <command> --help` for the exact installed command interface; [schema navigation](docs/reference/README.md#schema-boundaries) distinguishes configuration inputs from assembled jobs and output artifacts.

## Terminal progress and outcomes

`prep-subject`, `generate-chunks`, `generate-docx`, and `lab proofread` use the
same stage and chapter prefixes, announce a bounded processing failure when it
happens, and finish with an explicit `succeeded`, `failed`, or `incomplete`
outcome. Final summaries distinguish processing from publication, identify
reused, skipped, or pending work when applicable, and print available output
and report locations. Request and upload counts appear only where they are
measured; a completed Gemini request does not by itself mean that its response
passed proofreading validation.

On an interactive terminal, only a successful whole-command outcome is green;
immediate failures and failed or incomplete outcomes are red. Redirected output
is plain text. Set `NO_COLOR` to any value to disable color explicitly.

## Documentation map

The [CLI documentation index](docs/README.md) is the entry point for focused guides, operational runbooks, concepts, and reference material. Documentation and `gurubodh --help` describe the currently supported command surface.
