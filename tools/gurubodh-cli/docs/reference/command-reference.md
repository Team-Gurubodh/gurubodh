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
- `lab proofread`, `lab assemble-docx`, and `lab append-docx` are local, non-canonical tools.
- `compare-tokenizers` estimates BGE-M3 tokens for chapter text. It can call Sarvam only when both its API key and explicit external-API approval flags are supplied. Its progress is written to stderr; JSON output is available with `--format json`.

The former preparation aliases are retired; use `prep-subject` with explicit selectors. The accepted migration map and retirement decision are tracked in [#288](https://github.com/Team-Gurubodh/gurubodh/issues/288).

## Optional larger-input proofreading

`prep-subject` and `lab proofread` accept
`--proofreading-profile gemini-3.6-flash-large-input-v1`. For a subject, the same
profile can be selected in its manifest with
`"profile_overrides": {"proofreading": "gemini-3.6-flash-large-input-v1"}`.

This complete profile raises the local estimated input-token budget from 20,000
to 40,000 per minute. The current estimator assigns 37,500 tokens to 30,000
characters, so the larger budget accommodates the existing 30,000-character
limit. All other settings remain the same, including the 16,384 output-token
limit and 120-second request timeout. The default remains
`gemini-3.6-flash-v1`; selecting the optional profile does not increase the
provider's quota.
