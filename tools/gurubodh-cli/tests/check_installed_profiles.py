"""Run with an isolated installed interpreter; see the fixture README."""

import copy
from importlib.metadata import distribution
import json
from pathlib import Path
import sys
from unittest.mock import patch

import gurubodh.schema_validation as validation
from gurubodh.errors import ConfigurationError, ProcessingError


def check_profiles(fixture_root, install_root):
    with patch("socket.socket", side_effect=AssertionError("network forbidden")):
        for kind, profile_id in (
            ("proofreading", "gemini-3.6-flash-v1"),
            ("chunking", "bge-m3-v1"),
        ):
            filename = validation.COMPONENT_SCHEMAS[f"{kind}-profile"]
            path = validation.schema_path("job-components/schemas", filename).resolve()
            assert path.is_relative_to(install_root), path
            assert path.is_file()
            payload = json.loads((fixture_root / kind / f"{profile_id}.json").read_text())
            original = copy.deepcopy(payload)
            validation.validate_component(payload, f"{kind}-profile", expected_id=profile_id)
            assert payload == original
            for key in original[kind]:
                invalid = copy.deepcopy(original)
                del invalid[kind][key]
                try:
                    validation.validate_component(invalid, f"{kind}-profile", "installed fixture")
                except ConfigurationError as exc:
                    assert f"$.{kind}.{key} is required" in str(exc), exc
                else:
                    raise AssertionError(f"Missing {kind}.{key} passed installed validation")


def main():
    fixture_root = Path(sys.argv[1])
    install_root = Path(sys.prefix).resolve()
    assert Path(validation.__file__).resolve().is_relative_to(install_root), validation.__file__
    dist = distribution("gurubodh_cli")
    direct_url = json.loads(dist.read_text("direct_url.json"))
    assert not direct_url.get("dir_info", {}).get("editable", False)
    assert {"proofreading-profile", "chunking-profile"} <= validation.COMPONENT_SCHEMAS.keys()

    check_profiles(fixture_root, install_root)
    job_schema_dir = validation.schema_path("jobs", "prep_subject_job.schema.json").resolve().parent
    assert job_schema_dir.is_relative_to(install_root), job_schema_dir
    hidden = job_schema_dir.with_name("jobs-hidden-for-profile-check")
    job_schema_dir.rename(hidden)
    try:
        validation.schema_path.cache_clear()
        validation._validator.cache_clear()
        check_profiles(fixture_root, install_root)
    finally:
        hidden.rename(job_schema_dir)
        validation.schema_path.cache_clear()
        validation._validator.cache_clear()

    with patch("socket.socket", side_effect=AssertionError("network forbidden")):
        try:
            validation.validate_artifact({}, "chapter metadata")
        except ProcessingError:
            pass
        else:
            raise AssertionError("Artifact error domain changed")

    print("Installed profiles passed with job definition schemas present and absent: both kinds, 29 required settings, non-mutation, error domains.")
    print(f"Package: {validation.__file__}")


if __name__ == "__main__":
    main()
