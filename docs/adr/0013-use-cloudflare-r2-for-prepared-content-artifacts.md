# 0013 — Use Cloudflare R2 for Prepared Content Artifacts

## Status

Accepted

## Decision and rationale

Use private Cloudflare R2 for durable prepared-content storage, addressed by
bucket and object key through its S3-compatible API. Public object URLs are
optional and may be null. Local filesystem storage remains supported for
development and compatibility.

Preparation needs a handoff that survives individual machines and temporary
workspaces. Private bucket/key references let trusted downstream workflows
consume artifacts without making browser-facing public URLs part of the contract.
This qualifies the [AWS hosting direction](0003-use-aws-as-hosting-platform.md)
for prepared storage only; it does not select a CMS media provider.

## Tradeoff and review trigger

The CLI depends on an S3-compatible client and runtime Cloudflare credentials;
object keys become a compatibility boundary. Multi-object writes are non-atomic.
Reconsider if concurrent writers or stronger release recovery require versioned
or atomic publication.

The [prepared-content contract](../interfaces/prepared-content-artifacts.md)
owns artifact ownership, locale roots, readiness, and recovery obligations.
The [configuration reference](../../tools/gurubodh-cli/docs/reference/configuration.md#storage-and-library-roots)
owns bucket/prefix routing; [R2 operations](../../tools/gurubodh-cli/docs/operations/r2-production-runs.md)
owns execution procedures.
