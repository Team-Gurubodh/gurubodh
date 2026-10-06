# Decision-0004: Gurubodh CLI Container Publication and Runtime

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-08-19</date>
<owners>Gurubodh maintainers</owners>

## Decision and rationale

Use a CPU-only, bounded CLI batch container for operational R2 jobs while retaining
native Python for development/debugging. Immutable source-SHA tags and digest pins
make baked-in code reproducible. Credentials and content stay outside the image;
non-secret build provenance remains available for audits without Git metadata.

Publish tested amd64/arm64 images to GHCR. Under
[#310](https://github.com/Team-Gurubodh/gurubodh/issues/310), native architecture
and package-resource checks precede publication of the tested images without
rebuilding. This reduces the gap between verified and distributed runtime.
The [workflow](../../.github/workflows/gurubodh-cli-container.yml) owns exact
checks/tags/permissions; [container operations](../../tools/gurubodh-cli/docs/operations/r2-production-runs.md)
owns registry access, mounts, and run procedures.

## Tradeoff and review trigger

Container/cache maintenance adds operational work. Scheduling, workers, GPU images,
and atomic R2 releases are outside this runtime choice. Reconsider for a registry
policy change, GPU requirement, or orchestrated job model.
