# Getting started with Gurubodh CLI

This guide gets a contributor to a safe local `prep-subject` run. It does not publish to R2 or replace existing artifacts.

## Before you begin

Complete the local preparation prerequisites in [Environment setup](environment-setup.md), including the environment-only `GEMINI_API_KEY`. Then run the following from the monorepo root:

```bash
make cli-venv
. tools/gurubodh-cli/.venv/bin/activate
make cli-install
cd tools/gurubodh-cli
gurubodh --help
```

The editable install exposes `gurubodh` while keeping it linked to this checkout. Runtime versions, legacy-conversion Node requirements, credential handling, and virtual-environment repair guidance live in [Environment setup](environment-setup.md).

## Your first run

Choose a maintained subject and the `local` storage profile. Review its manifest and selected components before execution. Bind `GURUBODH_SOURCE_LIBRARY_ROOT` and `GURUBODH_CMS_LIBRARY_ROOT` to your absolute local library paths; these variables are required for local preparation.

```bash
gurubodh prep-subject \
  --subject sub123_spand_rahasya --language hi-IN --environment development --storage-profile local
```

The command validates and reads the source DOCX, prepares proofread canonical chapter text and metadata, and publishes a subject manifest only when all chapters succeed. It also writes audit reports. Continue with [Prepare a subject](workflows/prepare-a-subject.md) for outputs and recovery.

## Working directory and project root

Run maintained jobs from `tools/gurubodh-cli`. From somewhere else, pass the CLI project root explicitly:

```bash
gurubodh prep-subject \
  --project-root /path/to/gurubodh/tools/gurubodh-cli \
  --subject sub123_spand_rahasya --language hi-IN --environment development --storage-profile local
```

The CLI otherwise uses `GURUBODH_CLI_ROOT`, then walks upward to find `jobs/subjects/`.

## Next steps

- Read the subject manifest and selected components before changing a source, destination, locale, or model setting.
- Use R2 only through [R2 production runs](operations/r2-production-runs.md), after completing [Environment setup](environment-setup.md).
- Learn what a successful run publishes in [Artifact lifecycle](concepts/artifact-lifecycle.md).
