# Gurubodh CLI documentation

Use this directory by intent. The CLI README is the short orientation; these pages hold the details needed to run and operate the tool safely.

## First steps and workflows

- [Environment setup](environment-setup.md) — runtimes, credentials, model cache, Docker variables, and setup failures.
- [Getting started](getting-started.md) — install the CLI, understand job locations, and perform a safe local preparation run.
- [Prepare a subject](workflows/prepare-a-subject.md) — canonical preparation, proofreading, resume, and replacement behavior.
- [Generate chunks](workflows/generate-chunks.md) — derive semantic chunks from a prepared release.
- [Generate DOCX exports](workflows/generate-docx.md) — create rebuildable, human-readable chapter exports.
- [Lab tools](workflows/lab-tools.md) — local, non-canonical experiments.

## Operations and concepts

- [R2 production runs](operations/r2-production-runs.md) — immutable Docker images, R2 credentials, and the BGE-M3 cache volume.
- [Artifact lifecycle](concepts/artifact-lifecycle.md) — ownership, invalidation, readiness markers, locales, and audit reports.

## Reference

- [Reference index](reference/README.md) — job configuration, storage, and command-reference links.
- [Legacy DOCX conversion](reference/legacy-docx-conversion.md) — source conversion details.
- [Semantic chunking](reference/semantic-chunking.md) — local model and experimental-interface boundary.
- [Legacy font mapping status](reference/legacy-font-mapping-status-and-future-work.md) — implementation notes and known mapping risks; not an operator runbook.

## Documentation convention

Keep a fact authoritative in one focused page. Link to it from other guides instead of copying it. New maintained commands should add a row to the CLI README, a focused guide, and any required safety, recovery, or audit guidance.
