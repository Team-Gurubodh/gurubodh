# Semantic Chunking

Semantic chunking is an internal content capability for grouping
Hindi/Indic chapter text into semantically coherent chunks with local embedding
models.

The module lives under:

```text
gurubodh/ml/semantic_chunking/
```

It is installable as part of the `gurubodh` Python package. It is not yet
called by the existing DOCX preparation pipelines.

## Purpose

The module is being integrated for issue #130 so Gurubodh can evaluate a local
alternative to API-backed paragraph segmentation. It may support two related
future needs:

- display paragraphing for long chapter text that currently has no paragraphs;
- semantic chunks for later CMS ingestion, embeddings, and RAG workflows.

## Runtime

The content project now requires Python `>=3.12,<3.13`.

Semantic chunking dependencies are installed with the main content
package:

```text
numpy>=1.26,<2
transformers>=4.41,<4.50
sentence-transformers>=3.0,<4
```

`sentence-transformers` also brings heavier ML runtime dependencies. The first
run with the default model may download model files into the local Hugging Face
cache. This makes setup heavier than the earlier DOCX-only utility, but avoids a
remote paragraphing API call when local chunking quality is acceptable.

## Python API

Use one `SemanticChunker` instance across many documents so the embedding model
is loaded only once:

```python
from gurubodh.ml.semantic_chunking import SemanticChunkConfig, SemanticChunker

config = SemanticChunkConfig(
    threshold_percentile=82,
    min_chars=700,
    window_size=3,
)

chunker = SemanticChunker(config)
document = chunker.chunk_text(raw_text, source_name="chapter.txt")

for chunk in document.chunks:
    print(chunk.index, chunk.char_count, chunk.text)
```

## Standalone Evaluation

For local experiments with `.txt` files:

```bash
python -m gurubodh.ml.semantic_chunking.cli \
  --source-dir source \
  --output-dir semantic_chunks_bge_m3
```

This command writes exploratory JSON and Markdown outputs. These outputs are not
part of the existing content artifact contract.

## Integration Boundary

Current behavior returns reconstructed chunk text and sentence ranges. This is
useful for evaluating quality, but it is not yet the durable representation
Gurubodh should store for paragraph metadata.

Before semantic chunking output is written into chapter metadata or used for CMS
ingestion, modified Task 014 work should add exact `[start, end)` character
spans into the canonical chapter `.txt` string. Spans make the chunks verifiable
against the source text and preserve the existing Gurubodh principle that
prepared text artifacts remain authoritative.
