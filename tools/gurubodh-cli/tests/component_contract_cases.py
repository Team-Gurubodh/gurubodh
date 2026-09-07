"""Reuse S1–S3 validation cases under one all-seven independence boundary."""

from contextlib import contextmanager
from pathlib import Path
import unittest
from unittest.mock import patch

import gurubodh.schema_validation as validation
import test_profile_contracts as profiles
import test_subject_locale_contracts as subjects
import test_command_storage_contracts as commands


def validation_suite():
    suite = unittest.TestSuite()
    for case in (profiles.ProfileContractTests, subjects.SubjectLocaleContractTests,
                 commands.CommandStorageContractTests):
        for name in unittest.defaultTestLoader.getTestCaseNames(case):
            # These two S1 cases intentionally cross the separate complete-job boundary.
            if name not in {
                "test_fixtures_match_maintained_policies_and_validate_in_existing_jobs",
                "test_existing_error_domains_are_preserved",
            }:
                suite.addTest(case(name))
    return suite


@contextmanager
def without_job_schemas():
    original_path = validation.schema_path
    original_open = Path.open

    def component_path(kind, filename):
        if kind == "jobs":
            raise AssertionError("component validation requested a job schema")
        return original_path(kind, filename)

    def guarded_open(path, *args, **kwargs):
        if "config" in path.parts and "jobs" in path.parts:
            raise AssertionError("component validation opened a job schema")
        return original_open(path, *args, **kwargs)

    validation.schema_path.cache_clear()
    validation._validator.cache_clear()
    try:
        with patch.object(validation, "schema_path", side_effect=component_path), \
             patch.object(Path, "open", guarded_open), \
             patch("socket.socket", side_effect=AssertionError("network forbidden")):
            yield
    finally:
        original_path.cache_clear()
        validation._validator.cache_clear()
