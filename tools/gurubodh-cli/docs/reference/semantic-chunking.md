# Semantic chunking

Semantic chunking groups Hindi and Marathi chapter text into coherent chunks. Maintained `generate-chunks` jobs derive manifest-bound artifacts from a successful prepared release. See [Generate chunks](../workflows/generate-chunks.md) for the supported workflow; this page covers the local model boundary.

## Runtime and model cache

Semantic chunking is installed with the `gurubodh` package and requires Python `>=3.12,<3.13`. The BGE-M3 model loads lazily only when contextual similarity or tokenization is required; reuse a chunker instance across documents. Model-cache location, immutable revision, cached-only behavior, and Docker safeguards are defined in [Environment setup](../environment-setup.md).

## Supported interface

The config-driven `gurubodh generate-chunks` command is the only supported folder-level semantic-chunk workflow. The former unregistered module CLI and generic folder writer are retired; they produced a separate, non-canonical output shape with ambiguous ownership. Internal chunking classes remain implementation details of the maintained command and do not define another artifact contract.

Maintained chunk artifacts include model/configuration metadata, zero-based end-exclusive character spans, chunk checksums, estimated BGE-M3 token counts, and a source/chunks checksum round trip. Finalized embedding vectors are not persisted.

The token estimate is BGE-M3 input size without special tokens, not an API billing metric. It is distinct from the tokenization used by overlapping contextual windows while finding chunk boundaries.
