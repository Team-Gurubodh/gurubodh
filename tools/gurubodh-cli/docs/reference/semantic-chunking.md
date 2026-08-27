# Semantic chunking

Semantic chunking groups Hindi and Marathi chapter text into coherent chunks. Maintained `generate-chunks` jobs derive manifest-bound artifacts from a successful prepared release. See [Generate chunks](../workflows/generate-chunks.md) for the supported workflow; this page covers the local model boundary.

## Runtime and model cache

Semantic chunking is installed with the `gurubodh` package and requires Python `>=3.12,<3.13`. Before a local model operation, set its cache location:

```bash
export GURUBODH_MODEL_CACHE_DIR="$HOME/.cache/huggingface/hub"
```

The BGE-M3 model loads lazily only when contextual similarity or tokenization is required; reuse a chunker instance across documents. Maintained jobs require the immutable BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181` and normally set `local_files_only: true`. Cache bootstrap and Docker use are documented in [R2 production runs](../operations/r2-production-runs.md).

## Experimental interface

The package retains lower-level experimental helpers for local evaluation, but they are not exposed through the supported `gurubodh` command surface. Do not invoke an internal module for a maintained or publishable workflow; use the config-driven `generate-chunks` command instead.

The internal output contract includes model/configuration metadata, zero-based end-exclusive character spans, chunk checksums, estimated BGE-M3 token counts, and a source/chunks checksum round trip. Existing output is intentionally protected unless a caller explicitly requests replacement. Finalized embedding vectors are not persisted.

The token estimate is BGE-M3 input size without special tokens, not an API billing metric. It is distinct from the tokenization used by overlapping contextual windows while finding chunk boundaries.
