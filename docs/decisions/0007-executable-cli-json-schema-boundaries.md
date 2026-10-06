# Decision-0007: Executable Gurubodh CLI JSON Schema Boundaries

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-08-29</date>
<owners>Gurubodh maintainers</owners>

## Decision and rationale

Use executable Draft 2020-12 schemas as the structural authority. Repeating
selected schema constraints in loaders/writers allowed accepted input and
produced output to drift. Shared validation before typed conversion and artifact
serialization keeps invalid structures outside publication boundaries.

Current composed manifests, locales, command/environment/storage definitions,
and execution profiles validate against component schemas. Composition then
validates the in-memory result against retained assembled-job schemas. Governed
artifacts and the shared font policy also validate. Complete-job file execution
was retired under [#288](https://github.com/Team-Gurubodh/gurubodh/issues/288);
retaining those schemas does not restore it.

Python owns semantics schemas cannot express: safe paths, regex compilation,
locale/root relationships, checksum/content binding, and runtime model-cache
behavior. The [schema reference](../../tools/gurubodh-cli/docs/reference/README.md#schema-boundaries)
owns resource discovery links; [schema_validation.py](../../tools/gurubodh-cli/gurubodh/schema_validation.py)
owns shared validation/diagnostics across native, installed, and container use.

## Tradeoff and review trigger

Schemas must ship with the runtime and producers must remain covered by
[enforcement tests](../../tools/gurubodh-cli/tests/test_schema_validation.py).
Reconsider when adding a schema boundary, changing packaging, or moving a
semantic check into an executable structural contract.
