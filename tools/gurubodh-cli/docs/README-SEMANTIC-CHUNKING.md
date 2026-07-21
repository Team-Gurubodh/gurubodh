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

The Gurubodh CLI project now requires Python `>=3.12,<3.13`.

Semantic chunking dependencies are installed with the main Gurubodh CLI
package:

```text
numpy>=1.26,<2
transformers>=4.41,<4.50
sentence-transformers>=3.0,<4
```

`sentence-transformers` also brings heavier ML runtime dependencies. Semantic
chunking requires `GURUBODH_MODEL_CACHE_DIR` to point at the local model cache
before a command is run:

```bash
export GURUBODH_MODEL_CACHE_DIR=~/.cache/huggingface/hub
```

The BGE-M3 model is not loaded at import time or when lightweight config/parser
objects are constructed. It is loaded lazily only when semantic chunking needs
embeddings, and one `SemanticChunker` instance reuses the loaded model across
files in a run.

## Python API

Use one `SemanticChunker` instance across many documents so the embedding model
is loaded only once:

```python
from gurubodh.ml.semantic_chunking import SemanticChunkConfig, SemanticChunker

config = SemanticChunkConfig(
    threshold_percentile=80,
    min_chars=650,
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
gurubodh generate-chunks \
  --source-dir /Users/rajeev/Gurubodh_library/cms_library/39_aacharan_shaastra/chapters/text_and_metadata \
  --output-dir /Users/rajeev/Gurubodh_library/cms_library/39_aacharan_shaastra/chapters \
  --model-name BAAI/bge-m3 \
  --threshold-percentile 82 \
  --min-chars 700 \
  --window-size 3 \
  --batch-size 16 \
  --device cpu
```

This command writes exploratory JSON and Markdown outputs under
`semantic_chunks_bge_m3/` inside the requested output directory. These outputs
are not part of the existing content artifact contract. If that output directory
already contains files, the command fails unless `--overwrite` is supplied.
The command prints line-based progress while it runs, including model-cache
resolution, model loading, per-chapter read/segment/validate/write steps, and
final file/chunk totals.

## Integration Boundary

Current behavior returns chunk text, sentence ranges, exact zero-based
end-exclusive character spans into the source text, provider/model metadata,
and per-chunk checksums. Before writing a chapter's outputs, the command removes
Python-recognized Unicode whitespace with `str.isspace()`, hashes the source
text, hashes the ordered chunks, and requires those checksums to match.

The existing DOCX preparation pipelines do not call semantic chunking yet.
Future Task 014 integration should use the `ParagraphSegmenter` boundary rather
than directly constructing a model-specific `SentenceTransformer`.
