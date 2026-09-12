"""S4 executable selection examples and characterization, not a runtime resolver."""

import copy
import os
import tempfile
import unittest
from unittest.mock import patch

from gurubodh.config import prepare_prep_subject_job, prepare_generate_chunks_job
from gurubodh.errors import ConfigurationError
from gurubodh.schema_validation import validate_component
from test_command_storage_contracts import fixture


def example_job(root, command, settings):
    """Explicit small payload independent of production assembly (which is future work)."""
    job = {
        "schema_version": "1.5.0" if command == "prep-subject" else "1.2.0",
        "pipeline": "unicode-docx-ingest" if command == "prep-subject" else "generate-chunks",
        "source": {"backend": "local", "root_dir": root, "subject_dir": "explicit/root/hi-IN"},
        "destination": {"backend": "local", "root_dir": root, "subject_dir": "explicit/root/hi-IN"},
        "naming": {"category_code": "CAT001", "subject_code": "SUB123", "title_slug": "example",
                   "version": "01", "subversion": "02"},
    }
    if command == "prep-subject":
        job["source"] = {"backend": "local", "root_dir": root, "relative_path": "example.docx",
                         "font_encoding": "unicode", "file_format": "docx"}
        job["chapter_split"] = {"enabled": False}
        job["metadata_defaults"] = {"language": "hi-IN", "source_script": "Devanagari",
                                    "output_text_encoding": "UTF-8", "summary_chapter_markers": []}
        job["proofreading"] = copy.deepcopy(settings)
    else:
        job["naming"]["language"] = "hi-IN"
        job["chunking"] = copy.deepcopy(settings)
    return job


class SelectionMappingTests(unittest.TestCase):
    def test_preparation_semantics_and_runtime_cache_remain_separate(self):
        profile = fixture("proofreading/gemini-3.6-flash-v1.json")
        profile["proofreading"]["initial_retry_delay_seconds"] = 31
        # S1 checks explicit settings and progress/timeout semantics. The
        # pre-existing preparation boundary also checks retry-delay ordering.
        validate_component(profile, "proofreading-profile")
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ConfigurationError, "max_retry_delay_seconds"):
                prepare_prep_subject_job(example_job(root, "prep-subject", profile["proofreading"]))
            job = example_job(root, "generate-chunks",
                              fixture("chunking/bge-m3-semantic-window-v1.json")["chunking"])
            with patch.dict(os.environ, {"GURUBODH_MODEL_CACHE_DIR": root}):
                prepared = prepare_generate_chunks_job(job)
            self.assertEqual(prepared.semantic_chunk_config.cache_dir, root)
            self.assertEqual(prepared.to_payload(), job)
            self.assertNotIn("cache_dir", prepared.to_payload()["chunking"])

    def test_complete_profile_selection_examples_at_real_boundaries(self):
        # Each row independently states command/manifest/edition/run selections
        # and the winning ID. This is an oracle/example for #284, not its resolver.
        examples = (
            (None, None, None, "standard-v1"),
            ({}, {}, {}, "standard-v1"),
            ("careful-v1", None, None, "careful-v1"),
            ("careful-v1", "edition-v1", None, "edition-v1"),
            ("careful-v1", "edition-v1", "review-v1", "review-v1"),
            (None, "edition-v1", "review-v1", "review-v1"),
        )
        for kind, command_id, base_file, prepare, field in (
            ("proofreading", "prep-subject", "proofreading/gemini-3.6-flash-v1.json",
             prepare_prep_subject_job, "max_output_tokens"),
            ("chunking", "generate-chunks", "chunking/bge-m3-semantic-window-v1.json",
             prepare_generate_chunks_job, "batch_size"),
        ):
            base = fixture(base_file)
            profiles = {}
            for identity, value in (("standard-v1", 16), ("careful-v1", 8),
                                    ("edition-v1", 4), ("review-v1", 2)):
                document = copy.deepcopy(base)
                document["profile_id"] = identity
                document[kind][field] = value
                profiles[identity] = document
            with tempfile.TemporaryDirectory() as root:
                for manifest_choice, edition_choice, invocation_choice, expected in examples:
                    with self.subTest(kind=kind, expected=expected, choices=(
                            manifest_choice, edition_choice, invocation_choice)):
                        command = fixture(f"commands/{command_id}.json")
                        command["default_profiles"] = {kind: "standard-v1"}
                        manifest = fixture("subjects/aps-hindi.json")
                        edition = manifest["editions"]["hi-IN"]
                        for target, choice in ((manifest, manifest_choice), (edition, edition_choice)):
                            if choice is not None:
                                target["profile_overrides"] = {kind: choice} if isinstance(choice, str) else choice
                        validate_component(command, "command-definition")
                        validate_component(manifest, "subject-manifest")
                        selections = [command["default_profiles"], manifest.get("profile_overrides", {}),
                                      edition.get("profile_overrides", {}),
                                      {kind: invocation_choice} if isinstance(invocation_choice, str) else {}]
                        selected_id = next(layer[kind] for layer in reversed(selections) if kind in layer)
                        self.assertEqual(selected_id, expected)
                        selected = profiles[selected_id]
                        before = copy.deepcopy((command, manifest, profiles))
                        validate_component(selected, f"{kind}-profile", expected_id=selected_id)
                        job = example_job(root, command_id, selected[kind])
                        prepared = prepare(job)
                        self.assertEqual(prepared.to_payload()[kind], profiles[expected][kind])
                        self.assertEqual(prepared.to_payload(), job)
                        self.assertEqual((command, manifest, profiles), before)
                        # Earlier complete policies cannot fill a missing selected setting.
                        incomplete = copy.deepcopy(selected)
                        del incomplete[kind][field]
                        with self.assertRaises(ConfigurationError):
                            validate_component(incomplete, f"{kind}-profile")
                        incomplete_job = example_job(root, command_id, incomplete[kind])
                        with self.assertRaises(ConfigurationError):
                            prepare(incomplete_job)

    def test_manifest_profile_kinds_are_consumed_only_by_applicable_commands(self):
        manifest = fixture("subjects/unicode-bilingual.json")
        validate_component(manifest, "subject-manifest")
        self.assertEqual(set(manifest["profile_overrides"]), {"proofreading", "chunking"})
        for command_id, applicable in (("prep-subject", {"proofreading"}),
                                       ("generate-chunks", {"chunking"}), ("generate-docx", set())):
            command = fixture(f"commands/{command_id}.json")
            self.assertEqual(set(command["default_profiles"]), applicable)
            self.assertEqual(set(manifest["profile_overrides"]) & set(command["default_profiles"]), applicable)
        # Lab's shape and shared binding are covered by the S3 validator cases.
        # Inapplicable invocation flags are a future resolver/CLI rejection, not
        # a component-validator feature exercised by these examples.

    def test_retired_omission_allowances_fail_at_in_memory_preparation(self):
        from copy import deepcopy
        policy = fixture("proofreading/gemini-3.6-flash-v1.json")["proofreading"]
        with tempfile.TemporaryDirectory() as root:
            base = example_job(root, "prep-subject", policy)
            for section, field in (("source", "backend"), ("destination", "backend"),
                                   ("metadata_defaults", "summary_chapter_markers")):
                job = deepcopy(base)
                del job[section][field]
                with self.subTest(section=section, field=field), self.assertRaisesRegex(ConfigurationError, field):
                    prepare_prep_subject_job(job)
            for enabled in (True, False):
                job = deepcopy(base)
                job["chapter_split"] = {"enabled": enabled, "pattern_type": "regex", "pattern": "chapter"}
                with self.assertRaisesRegex(ConfigurationError, "flags"):
                    prepare_prep_subject_job(job)
            job = deepcopy(base)
            job["source"] = {"backend": "r2", "bucket": "example", "key": "source/example.docx",
                             "font_encoding": "unicode", "file_format": "docx"}
            with self.assertRaisesRegex(ConfigurationError, "url_base"):
                prepare_prep_subject_job(job)
            job["source"]["url_base"] = None
            self.assertEqual(prepare_prep_subject_job(job).to_payload(), job)
            job["destination"] = {"backend": "r2", "bucket": "example", "prefix": "artifacts",
                                  "subject_dir": job["destination"]["subject_dir"]}
            with self.assertRaisesRegex(ConfigurationError, "url_base"):
                prepare_prep_subject_job(job)
            job["destination"]["url_base"] = None
            self.assertEqual(prepare_prep_subject_job(job).to_payload(), job)


if __name__ == "__main__":
    unittest.main()
