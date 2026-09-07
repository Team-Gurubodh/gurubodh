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

## Distribution verification

Build in a temporary copy to keep build metadata out of the checkout. The default
`build` command creates an sdist, then its wheel, testing both distributions.
Install only schema-validation dependencies; invoke no models or providers.
Run from the CLI root using Python 3.12:

```bash
PROFILE_CHECK_ROOT=$(mktemp -d)
mkdir "$PROFILE_CHECK_ROOT/source"
cp -R gurubodh config pyproject.toml README.md "$PROFILE_CHECK_ROOT/source/"
cp -R tests/fixtures/job-components "$PROFILE_CHECK_ROOT/fixtures"
cp tests/check_installed_profiles.py "$PROFILE_CHECK_ROOT/check_installed_profiles.py"
cp tests/check_installed_subject_locales.py tests/test_subject_locale_contracts.py "$PROFILE_CHECK_ROOT/"
.venv/bin/python -m venv "$PROFILE_CHECK_ROOT/venv"
"$PROFILE_CHECK_ROOT/venv/bin/python" -m pip install build 'setuptools>=68' wheel 'jsonschema>=4.23,<5' 'referencing>=0.35,<1'
"$PROFILE_CHECK_ROOT/venv/bin/python" -m build --no-isolation --outdir "$PROFILE_CHECK_ROOT/dist" "$PROFILE_CHECK_ROOT/source"
"$PROFILE_CHECK_ROOT/venv/bin/python" -m pip install --no-deps "$PROFILE_CHECK_ROOT"/dist/*.whl
cd "$PROFILE_CHECK_ROOT"
"$PROFILE_CHECK_ROOT/venv/bin/python" -I -B check_installed_profiles.py fixtures
"$PROFILE_CHECK_ROOT/venv/bin/python" -I -B check_installed_subject_locales.py fixtures
```

The probes verify installed import/schema paths, reject editable installs, and
block networking. The S1 probe checks both profiles, all 29 missing-setting cases,
non-mutation, and artifact errors. It repeats profile checks with job definition
schemas temporarily absent, then restores them. Inspect both distributions for
all four job component schemas. The S2 probe runs the complete validation case
class (including standalone structural checks) with job schemas present and
physically absent. It deliberately excludes the mapping class, which is checked
separately in the checkout against existing job boundaries. #287 owns broader
catalog/container discovery.
