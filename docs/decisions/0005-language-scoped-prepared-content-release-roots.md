# Decision-0005: Language-Scoped Prepared Content Release Roots

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-08-26</date>
<owners>Gurubodh maintainers</owners>

## Decision and rationale

Make language the final segment of each prepared subject release root. Hindi
and Marathi must coexist without sharing canonical files, checkpoints, provenance,
derived outputs, or overwrite effects. Putting language above the full artifact
tree preserves relative paths while isolating command ownership.

Locale/template provenance affects checkpoint compatibility: a resumed job must
not silently switch proofreading language or instructions. Safe template identity
is recorded without retaining prompt bodies.

The [prepared contract](../interfaces/prepared-content-artifacts.md#command-ownership-and-locale-roots)
owns release obligations; [configuration](../../tools/gurubodh-cli/docs/reference/configuration.md)
and [preparation guidance](../../tools/gurubodh-cli/docs/workflows/prepare-a-subject.md#source-handling-and-migration)
own routing and legacy-location handling.

## Review trigger

Reconsider for new locales, cross-language editorial relationships, or versioned
release publication.
