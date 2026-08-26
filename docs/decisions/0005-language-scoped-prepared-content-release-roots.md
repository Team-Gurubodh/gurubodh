# Decision-0005: Language-Scoped Prepared Content Release Roots

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-08-26</date>
<owners>Gurubodh maintainers</owners>

## Context

Hindi and Marathi preparation for one subject must coexist without sharing
canonical artifacts, checkpoints, semantic chunks, overwrite effects, or audit
history. The earlier `{subject_dir}` artifact contract did not make language a
mandatory part of that release boundary.

## Decision

Treat each `{subject-group}/{language}` root as an independent prepared-content
release unit. Initially the only permitted languages are `hi-IN` and `mr-IN`.
The language is the final segment of `subject_dir`, while the subject grouping
remains above it:

```text
cms_library/{subject-group}/hi-IN/
cms_library/{subject-group}/mr-IN/
```

Every prep-subject-owned and generate-chunks-owned path stays beneath that
root, including canonical artifacts, manifests, semantic chunks, reports,
checkpoints, and workspaces. A job rejects unsafe nested paths and rejects a
language partition, prompt selection, metadata language, candidate manifest,
or generate-chunks source/destination root that does not agree with the
configured locale.

Proofreading uses an explicit locale template selected before each Gemini
request. Safe provenance records the locale and stable template ID, version,
and hash; it never records the prompt body. Template provenance is
output-affecting checkpoint compatibility data.

## Rationale

Putting language above the entire subject tree avoids shared canonical,
derived-output, report, state, and workspace paths. It preserves existing artifact-relative
contracts and lets command-scoped overwrite/invalidation safely operate only
within one language release.

## Impact

Existing unqualified Hindi artifacts are legacy locations. The CLI never moves
or deletes them automatically. Operators regenerate Hindi into `hi-IN`, verify
the new canonical manifest and audits, regenerate chunks, and retain legacy
artifacts until an explicit archival or deletion decision. An incomplete old
checkpoint cannot be resumed into a language root.

## Review Trigger

Review when supporting another locale, introducing cross-language editorial
relationships, or adding atomic/versioned release publication.
