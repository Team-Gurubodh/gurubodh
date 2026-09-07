"""Repeat S3 contract cases through a real non-editable installation."""

from importlib.metadata import distribution
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import gurubodh.schema_validation as validation


def main():
    install_root = Path(sys.prefix).resolve()
    assert Path(validation.__file__).resolve().is_relative_to(install_root), validation.__file__
    dist = distribution("gurubodh_cli")
    direct_url = json.loads(dist.read_text("direct_url.json"))
    assert not direct_url.get("dir_info", {}).get("editable", False)
    for kind in ("command-definition", "environment", "storage-profile"):
        path = validation.schema_path("job-components/schemas", validation.COMPONENT_SCHEMAS[kind]).resolve()
        assert path.is_relative_to(install_root) and path.is_file(), path

    # Only the validation case class is used; mapping cases need checkout/runtime dependencies.
    test_path = Path(__file__).with_name("test_command_storage_contracts.py")
    spec = importlib.util.spec_from_file_location("installed_s3_cases", test_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.FIXTURES = Path(sys.argv[1]).resolve()

    def run_cases():
        validation.schema_path.cache_clear()
        validation._validator.cache_clear()
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(module.CommandStorageContractTests)
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            result = unittest.TextTestRunner(verbosity=2).run(suite)
        assert result.wasSuccessful() and not result.skipped

    run_cases()
    jobs = validation.schema_path("jobs", "prep_subject_job.schema.json").resolve().parent
    assert jobs.is_relative_to(install_root), jobs
    hidden = jobs.with_name("jobs-hidden-for-s3-check")
    jobs.rename(hidden)
    try:
        run_cases()
    finally:
        hidden.rename(jobs)
        validation.schema_path.cache_clear()
        validation._validator.cache_clear()
    print("Installed S3 contracts passed with job schemas present and absent.")
    print(f"Package: {validation.__file__}")


if __name__ == "__main__":
    main()
