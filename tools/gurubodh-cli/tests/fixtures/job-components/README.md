# S1 profile contract fixtures

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

From the CLI root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -p test_profile_contracts.py -v
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
.venv/bin/python -m venv "$PROFILE_CHECK_ROOT/venv"
"$PROFILE_CHECK_ROOT/venv/bin/python" -m pip install build 'setuptools>=68' wheel 'jsonschema>=4.23,<5' 'referencing>=0.35,<1'
"$PROFILE_CHECK_ROOT/venv/bin/python" -m build --no-isolation --outdir "$PROFILE_CHECK_ROOT/dist" "$PROFILE_CHECK_ROOT/source"
"$PROFILE_CHECK_ROOT/venv/bin/python" -m pip install --no-deps "$PROFILE_CHECK_ROOT"/dist/*.whl
cd "$PROFILE_CHECK_ROOT"
"$PROFILE_CHECK_ROOT/venv/bin/python" -I -B check_installed_profiles.py fixtures
```

The probe verifies installed import/schema paths, rejects editable installs, and
blocks networking. It checks both profiles, all 29 missing-setting cases,
non-mutation, and artifact errors. It repeats profile checks with job definition
schemas temporarily absent, then restores them. Inspect both distributions for
the two job component schemas. #287 owns broader catalog/container discovery.
