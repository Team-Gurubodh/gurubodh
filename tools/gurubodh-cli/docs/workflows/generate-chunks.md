# Generate semantic chunks

`gurubodh generate-chunks` creates semantic chunk JSON from the canonical chapter manifest produced by a successful `prep-subject` run. It is a derived workflow: it never changes canonical chapter text or metadata, and it cannot run against incomplete or legacy prepared trees.

## Prerequisites

- A completed matching `prep-subject` release.
- A maintained job whose source and destination use the same language-qualified `subject_dir` and whose `naming.language` matches the manifest.
- The exact pinned BGE-M3 model snapshot in the configured local cache.

Maintained jobs use the immutable BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181` with `local_files_only: true`. Bootstrap or repair the cache deliberately before the job; normal jobs do not perform an unexpected model lookup. Full cache and container guidance is in [R2 production runs](../operations/r2-production-runs.md).

## Run a local job

```bash
export GURUBODH_MODEL_CACHE_DIR="$HOME/.cache/huggingface/hub"
gurubodh generate-chunks \
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/generate-chunks.local.json
```

The command validates the candidate manifest and its selected metadata/text pairs before initializing the model. It writes one `*.chunks.json` per chapter, a `semantic_chunks_manifest.json`, and run reports under:

```text
<subject-group>/<language>/chapters/semantic_chunks/
<subject-group>/<language>/run_reports/generate-chunks/
```

Chunk artifacts bind back to canonical content through checksums and content identity. The model may be used to find boundaries, but finalized embedding vectors are not persisted.

## Replacement and standalone experiments

Without `--overwrite`, an existing chunk output fails preflight. With it, only the command-owned semantic-chunk output (and the legacy combined-output location when present) is replaced. Do not run another writer for that subject and locale at the same time.

For the lower-level experimental boundary, see [Semantic chunking](../reference/semantic-chunking.md). Those results are non-canonical and are not preparation artifacts.
