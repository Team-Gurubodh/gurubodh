# Command reference

The installed CLI is authoritative for options and accepted syntax:

```bash
gurubodh --help
gurubodh prep-subject --help
gurubodh generate-chunks --help
gurubodh generate-docx --help
gurubodh models prepare --help
gurubodh models verify --help
gurubodh models check-updates --help
gurubodh config resolve --help
gurubodh lab --help
gurubodh lab proofread --help
gurubodh lab assemble-docx --help
gurubodh lab append-docx --help
gurubodh compare-tokenizers --help
```

## Maintained command families

- `prep-subject` reads a declared preparation pipeline and publishes canonical artifacts. See [Prepare a subject](../workflows/prepare-a-subject.md).
- `generate-chunks` derives manifest-bound semantic chunks. See [Generate chunks](../workflows/generate-chunks.md).
- `generate-docx` derives manifest-bound DOCX exports. See [Generate DOCX exports](../workflows/generate-docx.md).
- `models prepare` downloads or repairs only the required files for a validated pinned chunking profile and then verifies the result offline; `models verify` checks the same contract without network access or repair; `models check-updates` performs an advisory comparison of the pin with upstream repository history and file metadata. See [Manage the pinned model](../workflows/manage-model-cache.md).
- `config resolve` validates and prints composed configuration without executing a workflow; see below.
- `lab proofread`, `lab assemble-docx`, and `lab append-docx` are local, non-canonical tools.
- `compare-tokenizers` estimates BGE-M3 tokens for chapter text. It can call Sarvam only when both its API key and explicit external-API approval flags are supplied. Its progress is written to stderr; JSON output is available with `--format json`.

The former preparation aliases are retired; use `prep-subject` with explicit selectors. The accepted migration map and retirement decision are tracked in [#288](https://github.com/Team-Gurubodh/gurubodh/issues/288).

## Model commands

All three commands require `--profile ID` and accept `--project-root` for the normal
[project and packaged-resource discovery](configuration.md#project-and-resource-discovery).
The cache commands use `GURUBODH_MODEL_CACHE_DIR`, including the container's mounted
`/var/cache/gurubodh/models` contract. Initial support is limited to the validated,
immutable BGE-M3 SentenceTransformer profile. Unknown profiles, unsupported settings,
and non-commit revisions fail before artifact content is downloaded.

`models prepare` is the only command in this pair that uses the network. It resolves
file metadata at the exact profile revision, reports the selected allowlist and byte
plan, reuses valid content, downloads or repairs only required entries, and then runs
offline verification. It never falls back to a whole-repository snapshot.

`models verify` reads the locally prepared integrity contract, hashes every required
file, and performs a small encoding through the production embedding helper with
cached-only loading. It neither requests network metadata nor changes the cache.
Missing, damaged, or unloadable files fail with the matching `models prepare` command.

`models check-updates` needs network access but does not require, read, or change the
runtime model cache. It resolves upstream `main`, proves that the pin is in that
commit's history, and compares revision file metadata using the same required-runtime
allowlist as preparation. It may fetch only small configuration files into temporary
storage for architecture, embedding-dimension, and context-limit reporting; it never
downloads weights or initializes the model.

Both `current` and `update available` are successful advisory results with exit code
zero. Missing or divergent history, unavailable pins, authentication/network/API
failures, and other indeterminate checks report `unable to determine` and exit
nonzero with an `unable to check` status; they never fall back to `current`. A newer
commit can contain only model-card or repository metadata changes, so this command
does not call every newer revision a model release and makes no quality or
compatibility claim.

## Canonical command options

All three canonical commands require the four [composition selectors](configuration.md#selectors-and-ownership).
Use `--project-root` for [project discovery](configuration.md#project-and-resource-discovery)
and `--overwrite` to replace command-owned output as described in the workflow guides.

| Command | Additional options |
| --- | --- |
| `prep-subject` | `--proofreading-profile ID`; `--resume` for compatible incomplete checkpoints (mutually exclusive with `--overwrite`) |
| `generate-chunks` | `--chunking-profile ID`; `--chapters 001 002` |
| `generate-docx` | No profile or chapter selector |

Chunk chapter numbers must be unique, exact three-ASCII-digit strings. Omitting
`--chapters` selects the full candidate set; selecting a subset generates a
replacement chunk set for that selection, not an incremental append to existing
output. Source chapter existence is checked during execution, not configuration
inspection. Profile precedence and whole-profile replacement are defined in
[Configuration](configuration.md#selectors-and-ownership).

## Config resolve

From `tools/gurubodh-cli`, with the [used library-root variables](configuration.md#storage-and-library-roots)
set, inspect a maintained job:

```bash
gurubodh config resolve --command prep-subject \
  --subject sub123_spand_rahasya --language hi-IN \
  --environment development --storage-profile local --provenance \
  > /tmp/gurubodh-resolved.json 2> /tmp/gurubodh-provenance.json
```

On success, stdout contains only deterministic, validated assembled-job JSON.
`--provenance` adds separate JSON to stderr with selectors, selected profiles and
selection levels, component origins/digests, and library variable names. Resolved
job JSON includes concrete local library paths. Without `--provenance`, successful
inspection leaves stderr empty; on failure, stderr contains diagnostics instead.

The command validates selected components, composition, and the assembled job's
schema and configuration semantics. It does not read source content, create
library directories, initialize providers/storage/models, or validate live source
availability, credentials, services, or model-cache readiness. No provider keys
or downloaded model cache are required. Success is not an execution preflight.

The same applicable profile selectors and chunk chapter selection are accepted:

```bash
gurubodh config resolve --command generate-chunks \
  --subject sub123_spand_rahasya --language hi-IN \
  --environment development --storage-profile r2 \
  --chunking-profile bge-m3-semantic-window-v1 --chapters 001 002
```

There are no `--overwrite` or `--resume` options for inspection. Exported JSON is
inspection output only; the retired `--config` interface cannot execute it.
Run the canonical command with the same selectors to execute the job.

## Local tools

These commands do not use the canonical four-selector interface:

| Command | Input and relevant options |
| --- | --- |
| `lab proofread` | Required `--source DOCX --locale hi-IN --lab-root DIR`; optional `--project-root` and `--proofreading-profile` |
| `lab assemble-docx` | Positional `input_directory output`; optional `--overwrite` |
| `lab append-docx` | Positional `source destination`; `--page-break` (default) or `--no-page-break` |
| `compare-tokenizers` | Required `--source-file TXT` or `--source-dir DIR`; directory filters `--chapter` (repeatable) or `--chapters` take filenames/stems, not canonical chapter numbers |

Lab commands produce non-canonical local outputs. Proofreading uses the shared
[font policy](legacy-docx-conversion.md#source-font-safety-boundary) and requires
Gemini credentials. Assembly/append accept controlled Gurubodh DOCX exports.

Tokenizer comparison supports `--format text|json`, `--model-name`,
`--model-revision`, and `--local-files-only`. Sarvam comparison requires
`--include-sarvam --approve-external-api` and `SARVAM_API_KEY`; `--sarvam-model`
selects its model. These tokenizer options are separate from canonical chunking
profiles. See installed help for defaults.

See [local tool recipes](../workflows/local-tools.md) for inspection, invocation,
output verification, and recovery for all four local commands.

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
