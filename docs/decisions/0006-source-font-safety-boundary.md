# Decision-0006: Source Font Safety Boundary

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-08-28</date>
<owners>Gurubodh maintainers</owners>

## Context

Canonical content must not be produced from an unverified legacy-font mapping.
The previously bundled generic ShreeLipi converter could silently generate
incorrect Unicode text because ShreeLipi and Shree Dev variants do not share a
universal encoding. A job declaration alone also could not establish that a
DOCX actually used the declared source font.

## Decision

The CLI supports centrally approved Unicode source font families and APS source
font families only. It resolves the effective font of every text run before
conversion, proofreading, checkpoint creation, or canonical publication.
Unapproved families, including ShreeLipi/Sri-Lipi/Shree Dev variants, fail the
run without a job-level override.

`source.font_encoding: "shreelipi"` is removed from the prep-subject job
contract. This is an intentional breaking validation change: existing
ShreeLipi jobs fail rather than producing potentially corrupt content. The
approved Unicode allowlist remains centrally maintained in code and requires
maintainer review for additions.

## Impact

Operators continue to use `source.font_encoding: "unicode"` or `"aps"`.
When an unapproved font is detected, they must provide an approved source or
request review of a genuinely Unicode font family; they cannot bypass the
check in job JSON. ShreeLipi documents remain unsupported until exact
font-specific mappings and golden fixtures exist.

## Review Trigger

Revisit only when verified font-specific mappings, golden fixtures, and an
approved production-support decision are available for a new legacy family.
