# Command reference

The installed CLI is authoritative for options and accepted syntax:

```bash
gurubodh --help
gurubodh prep-subject --help
gurubodh generate-chunks --help
gurubodh generate-docx --help
gurubodh lab --help
```

## Maintained command families

- `prep-subject` reads a declared preparation pipeline and publishes canonical artifacts. See [Prepare a subject](../workflows/prepare-a-subject.md).
- `generate-chunks` derives manifest-bound semantic chunks. See [Generate chunks](../workflows/generate-chunks.md).
- `generate-docx` derives manifest-bound DOCX exports. See [Generate DOCX exports](../workflows/generate-docx.md).
- `lab proofread`, `lab assemble-docx`, and `lab append-docx` are local, non-canonical tools. See [Lab tools](../workflows/lab-tools.md).
- `compare-tokenizers` estimates BGE-M3 tokens for chapter text. It can call Sarvam only when both its API key and explicit external-API approval flags are supplied. Its progress is written to stderr; JSON output is available with `--format json`.

`legacy-convert` and `unicode-ingest` are deprecated strict preparation aliases. Use `prep-subject` for normal operations. Commands labelled `[planned]` in `gurubodh --help` are not supported workflows and have no operator guide yet.
