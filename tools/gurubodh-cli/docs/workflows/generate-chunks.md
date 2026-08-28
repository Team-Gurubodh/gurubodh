# Generate semantic chunks

`gurubodh generate-chunks` creates semantic chunk JSON from the canonical chapter manifest produced by a successful `prep-subject` run. It is a derived workflow: it never changes canonical chapter text or metadata, and it cannot run against incomplete or legacy prepared trees.

## Prerequisites

- A completed matching `prep-subject` release.
- A maintained job whose source and destination use the same language-qualified `subject_dir` and whose `naming.language` matches the manifest.
- The exact pinned BGE-M3 model snapshot in the configured local cache.

Configure and, when necessary, deliberately bootstrap that cache through [Environment setup](../environment-setup.md). Maintained jobs use cached-only loading, so a normal job never silently repairs or replaces its model files.

## Run a local job

After setting `GURUBODH_MODEL_CACHE_DIR` through [Environment setup](../environment-setup.md), run:

```bash
gurubodh generate-chunks \
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/generate-chunks.local.json
```

The command validates the candidate manifest and its selected metadata/text pairs before initializing the model. It generates one `*.chunks.json` per chapter and `semantic_chunks_manifest.json` in a unique staged workspace, validates the complete package, then revalidates the canonical release immediately before publication. The manifest is the readiness marker. Published output and run reports live under:

```text
<subject-group>/<language>/chapters/semantic_chunks/
<subject-group>/<language>/run_reports/generate-chunks/
```

Chunk artifacts bind back to canonical content through checksums and content identity. The model may be used to find boundaries, but finalized embedding vectors are not persisted.

## Replacement and standalone experiments

Without `--overwrite`, an existing chunk output fails preflight without modifying it. With `--overwrite`, the prior local chunk set remains in place through generation, staged validation, and source revalidation; publication then swaps only the complete `chapters/semantic_chunks/` directory. A failed pre-publication rerun therefore leaves the prior ready set intact. The unsupported legacy `chapters/semantic_chunks_and_embeddings/` location is not removed during preflight. On a successful overwrite it is removed after the v2 output publishes, and that cleanup is recorded in the audit.

For R2 overwrite, the old readiness manifest is removed before replacement objects upload, validated chunk artifacts upload next, and `semantic_chunks_manifest.json` publishes last. A failed upload leaves no readiness manifest for the partial replacement. This is a readiness protocol, not an atomic multi-object replacement; do not run another writer for that subject and locale at the same time.

Every success or failure writes JSON and Markdown audit reports. Failure reports include the active lifecycle state, bounded error information, the known prior/publication state, upload and deletion progress, and per-chapter progress. R2 failure reports are uploaded when the reporting path remains available.

For the lower-level experimental boundary, see [Semantic chunking](../reference/semantic-chunking.md). Those results are non-canonical and are not preparation artifacts.
