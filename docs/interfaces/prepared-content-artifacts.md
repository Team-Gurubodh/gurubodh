# Prepared Content Artifact Interface

<record_type>interface_contract</record_type>
<status>accepted</status>
<date>2026-07-08</date>
<owners>Gurubodh maintainers</owners>

## Purpose

This document defines the handoff contract for artifacts produced by
`tools/content` and consumed later by content ingestion, metadata
generation, metadata ingestion, and CMS-backed application workflows.

## Boundary

```text
Source DOCX storage
-> tools/content
-> prepared artifact storage
-> future ingestion and metadata workflows
```

Preparation may use temporary local files internally. Temporary paths must not
appear in generated metadata for R2-backed jobs.

## Storage Backends

Supported backends:

- `local` - development and compatibility filesystem storage.
- `r2` - Cloudflare R2 object storage using the S3-compatible API.

For R2, the development bucket is:

```text
gurubodh-library-dev
```

Source DOCX objects are expected under:

```text
source_library/
```

Prepared CMS-library artifacts are expected under:

```text
cms_library/
```

## Artifact Layout

Prepared artifact grouping is preserved as object-key prefixes:

```text
cms_library/{subject_dir}/full_subject/
cms_library/{subject_dir}/chapters/msword/
cms_library/{subject_dir}/chapters/text_and_metadata/
```

R2 prefixes are object-key strings, not real folders.

## Metadata References

Chapter metadata includes storage references for the source object and each
chapter/full-subject artifact.

R2 references use:

```json
{
  "backend": "r2",
  "bucket": "gurubodh-library-dev",
  "key": "cms_library/129_spand_rahasya/chapters/text_and_metadata/example.json",
  "url": null
}
```

Local references use:

```json
{
  "backend": "local",
  "path": "chapters/text_and_metadata/example.json",
  "url": null
}
```

URL values are optional in job configuration and nullable in generated metadata.
Consumers must treat bucket/key or local path references as canonical.

## Overwrite Behavior

The preparation tool does not archive existing output. If output already exists,
jobs fail unless `--overwrite` is supplied. For R2 destinations, existing object
keys are checked before upload and object replacement requires `--overwrite`.
R2 jobs also check the destination subject prefix before local processing starts
so a missing overwrite flag fails early instead of after artifact generation.
