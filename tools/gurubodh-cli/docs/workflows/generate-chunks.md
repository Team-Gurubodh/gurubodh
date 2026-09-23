# Generate semantic chunks

`gurubodh generate-chunks` creates semantic chunk JSON from the canonical chapter manifest produced by a successful `prep-subject` run. It is a derived workflow: it never changes canonical chapter text or metadata, and it cannot run against incomplete or legacy prepared trees.

## Prerequisites

- A completed matching `prep-subject` release.
- A maintained job whose source and destination use the same language-qualified `subject_dir` and whose `naming.language` matches the manifest.
- The exact pinned BGE-M3 model snapshot in the configured local cache.

Configure and, when necessary, deliberately prepare and verify that cache through
[Manage the model cache](manage-model-cache.md). Maintained jobs use cached-only
loading, so a normal job never silently repairs or replaces its model files.
The maintained profile intentionally runs on CPU; see
[CPU execution](../environment-setup.md#intentional-cpu-execution) for runtime
requirements and GPU support status.

## Run a local job

After setting the local CMS root and `GURUBODH_MODEL_CACHE_DIR` through
[Environment setup](../environment-setup.md), inspect then execute:

```bash
gurubodh config resolve --command generate-chunks \
  --subject sub123_spand_rahasya --language hi-IN \
  --environment development --storage-profile local --provenance
```

Require successful inspection and review the canonical source, destination, and
pinned chunking profile. This does not load the model or inspect source chapters.

```bash
gurubodh generate-chunks \
  --subject sub123_spand_rahasya --language hi-IN --environment development --storage-profile local
```

Use `--chapters 001 002` to select chapters and `--chunking-profile` to select a
complete profile; see [command options](../reference/command-reference.md#canonical-command-options).
The [storage reference](../reference/configuration.md#storage-and-library-roots)
explains required library roots and the local input used by `r2-output`.

The command validates the candidate manifest and its selected metadata/text pairs before initializing the model. It generates one `*.chunks.json` per chapter and `semantic_chunks_manifest.json` in a unique staged workspace, validates the complete package, then revalidates the canonical release immediately before publication. The manifest is the readiness marker. Published output and run reports live under:

```text
<subject-group>/<language>/chapters/semantic_chunks/
<subject-group>/<language>/run_reports/generate-chunks/
```

Chunk artifacts bind back to canonical content through checksums and content identity. The model may be used to find boundaries, but finalized embedding vectors are not persisted.

## Select chapters and a complete profile

Prerequisites: a ready canonical release containing chapters `001` and `002`,
and the selected profile's pinned cache. Inspect the same selection you execute:

```bash
gurubodh config resolve --command generate-chunks \
  --subject sub123_spand_rahasya --language hi-IN \
  --environment development --storage-profile local --provenance \
  --chunking-profile bge-m3-semantic-window-v1 --chapters 001 002
gurubodh generate-chunks \
  --subject sub123_spand_rahasya --language hi-IN \
  --environment development --storage-profile local \
  --chunking-profile bge-m3-semantic-window-v1 --chapters 001 002
```

Inspect the canonical manifest first to choose real chapter numbers; resolution
checks selector syntax, while execution checks existence. The profile is a
[whole-profile replacement](../reference/configuration.md#selectors-and-ownership).
Require a succeeded outcome, inspect the printed audit, and verify the published
chunk manifest contains exactly the requested chapters and matching source bindings.

If chunks already exist, the execution above fails preflight. Add `--overwrite`
only to deliberately replace the **entire chunk set** with this subset; unselected
old chunks are not retained. Omitting `--chapters` on a later overwrite rebuilds
the full set. There is no incremental append or chunk resume. For failure
recovery, inspect the audit and use the replacement rules below and
[recovery decisions](../operations/recovery.md).

## Replacement behavior

Without `--overwrite`, an existing chunk output fails preflight without modifying it. With `--overwrite`, the prior local chunk set remains in place through generation, staged validation, and source revalidation; publication then swaps only the complete `chapters/semantic_chunks/` directory. A failed pre-publication rerun therefore leaves the prior ready set intact. The unsupported legacy `chapters/semantic_chunks_and_embeddings/` location is not removed during preflight. On a successful overwrite it is removed after the v2 output publishes, and that cleanup is recorded in the audit.

For R2 overwrite, the old readiness manifest is removed before replacement objects upload, validated chunk artifacts upload next, and `semantic_chunks_manifest.json` publishes last. A failed upload leaves no readiness manifest for the partial replacement. This is a readiness protocol, not an atomic multi-object replacement; do not run another writer for that subject and locale at the same time.

Every success or failure writes JSON and Markdown audit reports. Failure reports include the active lifecycle state, bounded error information, the known prior/publication state, upload and deletion progress, and per-chapter progress. R2 failure reports are uploaded when the reporting path remains available.

The JSON audit's `job_identity.chunking_model.device` and the Markdown audit's
`Embedding device` line identify the selected device (`cpu` for the maintained
profile). Chunk artifacts and the chunk manifest also record `chunking.device`.

There is no supported standalone folder writer or module CLI. See [Semantic chunking](../reference/semantic-chunking.md) for the maintained model boundary.
