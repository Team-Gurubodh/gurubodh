"""Run all seven contracts together outside the checkout in a non-editable wheel."""

from importlib.metadata import distribution
import json
import shutil
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import gurubodh.schema_validation as validation
from gurubodh.errors import ConfigurationError, ProcessingError


def main():
    install_root = Path(sys.prefix).resolve()
    assert Path(validation.__file__).resolve().is_relative_to(install_root), validation.__file__
    dist = distribution("gurubodh_cli")
    direct_url = json.loads(dist.read_text("direct_url.json"))
    assert not direct_url.get("dir_info", {}).get("editable", False)
    # Only copied test modules/fixtures are added; Gurubodh was imported from the
    # installation first. -I keeps checkout/PYTHONPATH imports out of the probe.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import component_contract_cases as cases
    import test_component_contract_completion as completion

    fixtures = Path(sys.argv[1]).resolve()
    for module in (cases.profiles, cases.subjects, cases.commands):
        module.FIXTURES = fixtures
    cases.profiles.CLI_ROOT = install_root
    for filename in completion.SCHEMAS.values():
        path = validation.schema_path("job-components/schemas", filename).resolve()
        assert path.is_relative_to(install_root) and path.is_file(), path

    def run_cases():
        validation.schema_path.cache_clear()
        validation._validator.cache_clear()
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(completion.AllComponentContractTests)
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            result = unittest.TextTestRunner(verbosity=2).run(suite)
        assert result.wasSuccessful() and not result.skipped
        for name, module in tuple(sys.modules.items()):
            if name == "gurubodh" or name.startswith("gurubodh."):
                assert Path(module.__file__).resolve().is_relative_to(install_root), name

    # Domain checks deliberately use the separate job/artifact boundary, before
    # removing job schemas. The component-only suite never invokes validate_job.
    for validate, name, error_type in (
        (validation.validate_job, "prep-subject", ConfigurationError),
        (validation.validate_artifact, "chapter metadata", ProcessingError),
    ):
        try:
            validate({}, name)
        except error_type:
            pass
        else:
            raise AssertionError(f"missing {error_type.__name__}")
    run_cases()
    jobs = validation.schema_path("jobs", "prep_subject_job.schema.json").resolve().parent
    assert jobs.is_relative_to(install_root), jobs
    hidden = jobs.with_name("jobs-hidden-for-s4-check")
    # OverlayFS may reject a directory rename from a lower image layer (EXDEV).
    # shutil.move preserves the physical-absence check on those Docker engines.
    shutil.move(jobs, hidden)
    try:
        assert not jobs.exists()
        run_cases()
    finally:
        shutil.move(hidden, jobs)
        validation.schema_path.cache_clear()
        validation._validator.cache_clear()
    print(f"All seven schemas passed; {cases.validation_suite().countTestCases()} reused validation cases "
          "per run, with job schemas present and physically absent.")
    print(f"Installed package: {validation.__file__}")


if __name__ == "__main__":
    main()
