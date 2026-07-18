# 0013 - Use Cloudflare R2 for Prepared Content Artifacts

## Status

Accepted

## Context

The content workflow produces CMS-ingestion-ready artifacts from
source DOCX files. Local filesystem paths are useful for development, but they
are not durable enough to become the long-term handoff contract between
preparation, ingestion, CMS-backed applications, and future metadata workflows.

Prepared artifacts must be addressable without assuming public object URLs.
Cloudflare R2 provides S3-compatible object storage and can keep objects
private while exposing stable bucket/key references to trusted server-side
workflows.

## Decision

Use Cloudflare R2 as the durable object storage backend for prepared content
artifacts. The development bucket is `gurubodh-library-dev`.

Prepared content jobs may still use a local filesystem backend for development
and backward compatibility. R2 jobs use object keys as canonical storage
references:

```text
source_library/
cms_library/
```

Prepared artifact keys preserve the existing local artifact grouping under each
subject:

```text
cms_library/{subject_dir}/full_subject/
cms_library/{subject_dir}/chapters/msword/
cms_library/{subject_dir}/chapters/text_and_metadata/
```

Metadata stores storage references containing backend, bucket, object key, and
an optional nullable URL. Public object URLs are not required.

## Consequences

**Positive**
- Prepared artifacts have durable bucket/key references independent of local
  machines and temporary processing paths.
- Future ingestion can consume private R2 objects through server-side access
  rather than browser-facing public URLs.
- Local filesystem jobs remain available for development and compatibility.

**Negative**
- R2 workflows require Cloudflare credentials in the runtime environment.
- The preparation tool now depends on an S3-compatible client library.
- Object keys become part of the handoff contract and must be changed carefully.

**Alternatives Considered**
- **Local filesystem only** - simplest for development, but not durable across
  machines, CI, or future ingestion workers.
- **Public R2 URLs in metadata** - convenient for browser access, but not needed
  for private-bucket CMS ingestion and creates the wrong downstream assumption.
