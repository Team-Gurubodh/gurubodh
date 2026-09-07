# Job component contract fixtures

## S1 profiles

These independent fixtures are not a production catalog.
`proofreading/gemini-3.6-flash-v1.json` declares the accepted Gemini policy;
`chunking/bge-m3-v1.json` preserves the maintained BGE-M3 settings.

`tests/test_profile_contracts.py` mutates one property per invalid case, with
expectations independent of the schemas. Cases cover every envelope/setting
deletion, unknown root/nested fields, wrong kinds/versions, unsafe or unversioned
IDs, invalid objects/types/constants/bounds, and timeout/interval conflicts.
Tests also cover nullable devices, false booleans, non-mutation, resource-ID
matching, local property ownership, missing schemas, deterministic diagnostics,
and maintained-job compatibility. Each schema runs through plain Draft 2020-12
validation and the shared validator with job definition schema access forbidden.

## S2 subjects and locales

`subjects/aps-hindi.json` declares APS/Hindi with literal splitting and no
profile overrides. `subjects/unicode-bilingual.json` declares Unicode/Hindi
with regex splitting and Unicode/Marathi with disabled splitting, independent
releases, and manifest/edition profile selections. `locales/hi-IN.json` and
`locales/mr-IN.json` declare the metadata and markers specified for #284.
All are test fixtures, not maintained catalog entries.

`tests/test_subject_locale_contracts.py` independently enumerates required fields
and mutates fixtures for invalid types, versions, identities, paths, encodings,
locale declarations, split shapes, flags, and profile references. Structural
rejections run through standalone Draft 2020-12 and the shared validator;
Python regex syntax is a separate semantic check. Tests assert non-mutation,
safe diagnostics, local property ownership, and forbidden job-schema access.
Mapping tests separately use real preparation functions for all three commands,
including prep local/R2 source shapes, without executing sources or providers.

From the CLI root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p test_profile_contracts.py -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p test_subject_locale_contracts.py -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p test_schema_validation.py -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -v
```

## S3 and S4 combined verification

S3 fixtures add four command branches, development stores, and all three storage
profiles. Their authoritative contract is [#296](https://github.com/Team-Gurubodh/gurubodh/issues/296).
S4 reuses the S1–S3 validation cases in `component_contract_cases.py` under one
job-schema access prohibition, including standalone structural failures for all
profile cases. Semantic interval/regex checks remain distinct from JSON Schema.
The combined ownership check compares raw schema documents to cached validators
and rejects external property references/default annotations. Separate mapping
tests cover the documented field inventory, the existing 27-case matrix, twelve
whole-profile selection examples, applicability, legacy complete-job shapes,
preparation retry ordering, and the separate runtime model cache.
Selection examples are contract oracles for #284, not a production resolver.

Focused checkout checks (run the full CLI suite above as well):

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p 'test_component*.py' -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p 'test_command_storage*.py' -v
```

## Distribution verification

Build in a temporary copy to keep build metadata out of the checkout. The default
`build` command creates an sdist, then its wheel, testing both distributions.
Install only schema-validation dependencies; invoke no models or providers.
Run these commands from the CLI root using Python 3.12:

```bash
PROFILE_CHECK_ROOT=$(mktemp -d)
mkdir "$PROFILE_CHECK_ROOT/source"
cp -R gurubodh config pyproject.toml README.md "$PROFILE_CHECK_ROOT/source/"
cp -R tests/fixtures/job-components "$PROFILE_CHECK_ROOT/fixtures"
cp tests/check_installed_components.py tests/check_component_distributions.py tests/component_contract_cases.py tests/test_component_contract_completion.py tests/test_profile_contracts.py tests/test_subject_locale_contracts.py tests/test_command_storage_contracts.py "$PROFILE_CHECK_ROOT/"
.venv/bin/python -m venv "$PROFILE_CHECK_ROOT/venv"
"$PROFILE_CHECK_ROOT/venv/bin/python" -m pip install build 'setuptools>=68' wheel 'jsonschema>=4.23,<5' 'referencing>=0.35,<1'
"$PROFILE_CHECK_ROOT/venv/bin/python" -m build --no-isolation --outdir "$PROFILE_CHECK_ROOT/dist" "$PROFILE_CHECK_ROOT/source"
"$PROFILE_CHECK_ROOT/venv/bin/python" -B tests/check_component_distributions.py config/job-components/schemas "$PROFILE_CHECK_ROOT"/dist/*.tar.gz "$PROFILE_CHECK_ROOT"/dist/*.whl
"$PROFILE_CHECK_ROOT/venv/bin/python" -m pip install --no-deps "$PROFILE_CHECK_ROOT"/dist/*.whl
cd "$PROFILE_CHECK_ROOT"
"$PROFILE_CHECK_ROOT/venv/bin/python" -I -B check_installed_components.py fixtures
```

The probe runs the all-seven ownership check and 44 reused validation methods
with job schemas present, then repeats with them physically absent. Imports and
schema locations must originate in the installation outside the checkout; all
validation runs block networking. Job/artifact domain checks occur separately
before hiding job schemas. No mapping case runs with job schemas absent.
The distribution checker compares every component schema byte-for-byte against
the checkout in both the sdist and its wheel. The full CLI suite separately
includes all 26 maintained jobs, preparation, fonts, checkpoints, and imports.

The earlier S1/S2/S3 probes remain available as `check_installed_profiles.py`,
`check_installed_subject_locales.py`, and `check_installed_command_storage.py`.
The combined probe covers their component-validation scope; broader catalog
and container discovery belong to #287.
