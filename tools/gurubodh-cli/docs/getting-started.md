# Getting started with Gurubodh CLI

This guide gets a contributor to a safe local `prep-subject` run. It does not publish to R2 or replace existing artifacts.

## Before you begin

You need Python 3.12, the repository checkout, and a Gemini API key supplied only through `GEMINI_API_KEY`. Run the following from the monorepo root:

```bash
make cli-venv
. tools/gurubodh-cli/.venv/bin/activate
make cli-install
cd tools/gurubodh-cli
gurubodh --help
```

The editable install exposes `gurubodh` while keeping it linked to this checkout. If a virtual environment was moved from an older path, recreate it or run the documented editable install again so generated wrappers point to the current checkout.

## Your first run

Choose a maintained `.local.json` job. It reads local input and writes local artifacts. Its source and destination paths are deliberate project data, so review the job before executing it.

```bash
export GEMINI_API_KEY=...
gurubodh prep-subject \
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.local.json
```

The command validates and reads the source DOCX, prepares proofread canonical chapter text and metadata, and publishes a subject manifest only when all chapters succeed. It also writes audit reports. Continue with [Prepare a subject](workflows/prepare-a-subject.md) for outputs and recovery.

## Working directory and project root

Run maintained jobs from `tools/gurubodh-cli`. From somewhere else, pass the CLI project root explicitly:

```bash
gurubodh prep-subject \
  --project-root /path/to/gurubodh/tools/gurubodh-cli \
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.local.json
```

The CLI otherwise uses `GURUBODH_CLI_ROOT`, then walks upward to find both `config/jobs/prep_subject_job.schema.json` and `jobs/subjects/`. Relative job paths resolve from the current directory when possible, then from that project root.

## Next steps

- Read the job and its schema before changing a source, destination, locale, or model setting: [Job configurations](reference/job-configurations.md).
- Use R2 only through [R2 production runs](operations/r2-production-runs.md).
- Learn what a successful run publishes in [Artifact lifecycle](concepts/artifact-lifecycle.md).
