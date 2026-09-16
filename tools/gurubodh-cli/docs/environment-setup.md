# Environment setup

This is the authoritative guide to the local and container environment needed to run Gurubodh CLI. Read it before a new workflow and return to it when setting up another machine. The workflow guides explain what a command does; this page explains the runtime, credentials, caches, and environment variables it depends on.

## Choose your execution environment

| Task | Runtime | Credentials | Model cache | Additional requirement |
| --- | --- | --- | --- | --- |
| Local `prep-subject`, Unicode source | Python 3.12 virtual environment | `GEMINI_API_KEY` | None | Local source and destination paths from the job |
| Local `prep-subject`, APS source | Python 3.12 virtual environment | `GEMINI_API_KEY` | None | Local Node installation for the bundled converter |
| Local `generate-chunks` | Python 3.12 virtual environment | None | `GURUBODH_MODEL_CACHE_DIR` with the job's pinned snapshot | A completed matching preparation release |
| Local `generate-docx` | Python 3.12 virtual environment | None | None | A completed matching preparation release |
| Local `lab proofread` | Python 3.12 virtual environment | `GEMINI_API_KEY` | None | Node only when a legacy-font source is detected |
| R2 `prep-subject` | Pinned Docker image | Gemini and Cloudflare R2 variables | None | One writer for the subject and locale |
| R2 `generate-chunks` | Pinned Docker image | Cloudflare R2 variables | Mounted BGE-M3 cache; `HF_HUB_OFFLINE=1` | A completed matching preparation release |
| R2 `generate-docx` | Pinned Docker image | Cloudflare R2 variables | None | A completed matching preparation release |

The [configuration reference](reference/configuration.md#storage-and-library-roots) owns environment/storage terminology, command-specific library-root requirements, and path routing. Configuration never contains credentials.

## Local development runtime

The CLI supports Python `>=3.12,<3.13`. From the monorepo root, create and install the editable local package:

```bash
make cli-venv
. tools/gurubodh-cli/.venv/bin/activate
make cli-install
cd tools/gurubodh-cli
gurubodh --help
```

The editable install keeps the `gurubodh` command linked to the checked-out source. If the virtual environment was copied or moved, recreate it or run `make cli-install` again so its generated wrappers use the current path.

Installation also provides the Draft 2020-12 `jsonschema` runtime and bundles
the component catalog, component/job/artifact schemas, and shared source-font policy with its schema.
If a command reports a missing or invalid bundled policy or schema, reinstall
the package from a complete checkout or image; do not copy individual resource
files into the environment by hand.

Unicode-only preparation needs no local Node installation. APS conversion runs the bundled JavaScript converter through `node`. Install Node.js 22 or 24 from [nodejs.org](https://nodejs.org/en/download), ensure `node` is on `PATH`, then run:

```bash
node --version
gurubodh aps check
```

The CLI accepts Node.js 22.x and 24.x. The APS golden mapping cases were run with Node.js 22.23.2 in the local CLI image and Node.js 24.16.0 locally; these are the tested patch versions, not a claim that every patch release was tested. The diagnostic converts the bundled APS sample `efkeâ&` and succeeds only when the result is exactly `र्कि`. It needs no source DOCX, project configuration, or credentials. An APS job checks Node before conversion; a missing executable reports installation and `PATH` guidance, and an unsupported version reports its detected version. The production image already includes Node 22.

Run maintained subjects from `tools/gurubodh-cli`. From another directory, pass `--project-root /path/to/gurubodh/tools/gurubodh-cli`; [Configuration](reference/configuration.md#project-and-resource-discovery) explains project and resource discovery.

## Credentials and secret handling

Set credentials in the calling shell or in a local, untracked environment file. Never put a value in job JSON, committed documentation, a container image, or a run report.

### Gemini

`prep-subject` and `lab proofread` require Gemini proofreading credentials:

```bash
export GEMINI_API_KEY=...
```

Preparation is strict: a missing or invalid key fails the run before canonical artifacts are published. `generate-chunks` and `generate-docx` do not use Gemini.

### Cloudflare R2

Any R2 source or destination requires all three variables:

```bash
export CLOUDFLARE_R2_ACCOUNT_ID=...
export CLOUDFLARE_R2_ACCESS_KEY_ID=...
export CLOUDFLARE_R2_SECRET_ACCESS_KEY=...
```

Pass them into a container by name with Docker `--env`, not by placing values in a command or job file. R2 stores objects rather than real directories; the job configuration owns the bucket, key/prefix, and language-qualified subject path.

## BGE-M3 model cache

`generate-chunks` needs the exact BGE-M3 snapshot selected by its maintained job. Set the local cache root before running it:

```bash
export GURUBODH_MODEL_CACHE_DIR="$HOME/.cache/huggingface/hub"
```

Maintained jobs use a full immutable Hugging Face revision and `local_files_only: true`. That combination makes runs reproducible: they use the already-downloaded snapshot and fail instead of quietly fetching different model files. The model-cache commands resolve that pin from the selected validated chunking profile; current maintained jobs use `bge-m3-semantic-window-v1`.

Prepare or repair the exact allowlisted runtime files deliberately, not during a
maintained run. Preparation requires network access and enough disk space for
the selected weights. It reports the revision-derived artifact size and remaining
download bytes before downloading content, reuses valid cache entries, and finishes
only after offline verification succeeds:

```bash
gurubodh models prepare --profile bge-m3-semantic-window-v1
gurubodh models verify --profile bge-m3-semantic-window-v1
```

`models verify` performs no downloads or repairs: it checks the prepared integrity
contract and required files, then loads the pinned model through the production
embedding path for a small offline encoding check. A cache directory's existence
alone is insufficient. See [Manage the model cache](workflows/manage-model-cache.md)
for command behavior and recovery, and [Docker and R2 operations](operations/r2-production-runs.md#bootstrap-the-model-cache)
for the mounted-volume form. Local and container workflows use the same pinned snapshot.

### `HF_HUB_OFFLINE=1`

Set this only for an R2 container chunk-generation run after its mounted cache is known to contain the required snapshot:

```bash
--env HF_HUB_OFFLINE=1
```

It instructs the Hugging Face Hub client not to make network requests. It is a defence-in-depth safeguard alongside the job's `local_files_only: true`: a chunk job or `models verify` invocation either uses the pinned cache volume or fails clearly. It does not download, populate, or repair the cache. Do not set it for `models prepare`, which must retrieve pinned-revision metadata and any missing or damaged required files.

## Docker execution environment

Production R2 jobs use the CPU-only `ghcr.io/team-gurubodh/gurubodh-cli` image, pinned by an immutable digest or `sha-<full-git-sha>` tag. Do not use a mutable tag. The image provides Python and Node, runs as a non-root user, and contains no credentials, content artifacts, or model weights.

For container chunk jobs, mount the BGE-M3 cache at `/var/cache/gurubodh/models`. A named volume is the usual choice:

```bash
docker volume create gurubodh-bge-m3-cache
```

`PYTHONUNBUFFERED=1` is optional but recommended for long-running containers: it makes Python logs appear immediately rather than waiting for an output buffer to fill. Full image build, cache bootstrap, and R2 command examples are in [Docker and R2 operations](operations/r2-production-runs.md).

Do not mount a working checkout over `/opt/gurubodh-cli` in production. The image's baked source revision is part of the audit provenance.

## Common setup failures

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| `gurubodh` is missing or points at an old checkout | Virtual environment not activated or was moved | Activate it; recreate it or rerun `make cli-install` |
| Preparation stops before publishing | Missing/invalid `GEMINI_API_KEY`, or an invalid proofreading response | Verify the environment variable and inspect the run report; use `--resume` only for a compatible incomplete run |
| Legacy conversion cannot start | `node` is missing from `PATH` or has an incompatible version | Install Node.js 22 or 24, ensure `node` is on `PATH`, then run `gurubodh aps check` |
| Chunk generation cannot find model files | Cache variable is unset, incomplete, or does not contain the profile's pinned revision | Set `GURUBODH_MODEL_CACHE_DIR`; run `gurubodh models prepare --profile bge-m3-semantic-window-v1` |
| Offline verification or container chunk run fails | Required files are missing, damaged, or unloadable | Repair with `models prepare` without `HF_HUB_OFFLINE=1`, rerun `models verify`, then retry the maintained job |
| R2 access fails | One or more R2 variables are absent or invalid | Re-export all three R2 variables in the calling environment; do not place them in the job |

Once the environment is ready, continue with [Getting started](getting-started.md) for the first safe local run, or select the relevant workflow from the [documentation index](README.md).
