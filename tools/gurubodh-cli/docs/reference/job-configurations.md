# Job configurations

Maintained jobs live below `jobs/subjects/<subject-group>/<language>/`. Read a job and its matching schema before changing it. Job JSON may contain paths and operational settings, but never credentials.

## Select a backend

| Filename convention | Source | Destination |
| --- | --- | --- |
| `*.local.json` | local | local |
| `*.r2-output.json` | local | Cloudflare R2 |
| `*.r2.json` | Cloudflare R2 | Cloudflare R2 |

Local source configuration combines `root_dir` and `relative_path`; local destination configuration combines `root_dir` and `subject_dir`. An R2 source uses `bucket` and object `key`. An R2 destination uses `bucket`, optional prefix, and `subject_dir`; R2 has object keys, not real folders.

All output layouts preserve the language-qualified subject root:

```text
cms_library/<subject-group>/<language>/
```

`subject_dir` must be a safe POSIX-relative nested path, retain a subject grouping, and end with the configured language. Absolute paths, empty segments, `.`, `..`, and backslashes are rejected. In a chunk job, source and destination must name the same language-qualified subject directory and `naming.language` must match the prepared manifest.

## Credentials

R2 jobs receive credentials from the calling environment:

```bash
export CLOUDFLARE_R2_ACCOUNT_ID=...
export CLOUDFLARE_R2_ACCESS_KEY_ID=...
export CLOUDFLARE_R2_SECRET_ACCESS_KEY=...
```

Preparation and lab proofreading read `GEMINI_API_KEY` from the environment. Do not put these values in JSON, documentation, images, shell history, or the repository.

## Schema and artifact references

Use the schemas in `config/jobs/` for required fields and validation. Generated artifact schemas are in `config/artifacts/`; their lifecycle and ownership are explained in [Artifact lifecycle](../concepts/artifact-lifecycle.md).
