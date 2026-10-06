# Decision-0003: Prepared Artifact Ownership and Lifecycle

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-08-02</date>
<owners>Gurubodh maintainers</owners>

## Decision and rationale

Give each command explicit ownership within a locale-scoped prepared release;
no command owns the whole subject tree. Canonical proofreading output,
provenance, derived artifacts, and audits have different lifetimes. Deleting a
subject tree during overwrite would destroy another command's output or audit
history.

Validate all required chapters before canonical publication. Successful canonical
replacement invalidates dependent outputs; staging failures preserve prior files.
Readiness gates prevent consumers from treating incomplete publication as content.
This protects recovery and audit history without prematurely introducing versioned
releases and a current pointer.

The [prepared-content contract](../interfaces/prepared-content-artifacts.md)
owns paths, consumption gates, invalidation, and recovery obligations. See
[locale-isolation rationale](0005-language-scoped-prepared-content-release-roots.md).

## Review trigger

Reconsider when concurrent writers, CMS ingestion, or production recovery require
atomic/versioned publication.
