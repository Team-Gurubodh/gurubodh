"""S3/S4 fixture mappings at existing job boundaries, without a production resolver."""

import copy
import tempfile
import unittest
from pathlib import Path

from gurubodh.config import (
    prepare_generate_chunks_job, prepare_generate_docx_job, prepare_prep_subject_job,
)
from gurubodh.errors import ConfigurationError
from gurubodh.schema_validation import validate_component
from test_command_storage_contracts import fixture, ROLE_FIELDS, ROUTES


class CommandStorageMappingTests(unittest.TestCase):
    def test_all_commands_routes_and_editions(self):
        prepare = {"prep-subject": prepare_prep_subject_job,
                   "generate-chunks": prepare_generate_chunks_job,
                   "generate-docx": prepare_generate_docx_job}
        # Expected locations/naming are independent of the fixture mapping below.
        examples = (
            ("subjects/aps-hindi.json", "hi-IN", "legacy-docx-to-unicode",
             "library/aps_example/hi-IN", "source_library/001_aps/legacy fonts/प्रबोधन.docx",
             {"category_code": "CAT001", "subject_code": "SUB001", "title_slug": "aps-example",
              "version": "01", "subversion": "01"}),
            ("subjects/unicode-bilingual.json", "hi-IN", "unicode-docx-ingest",
             "library/spand/hi-IN", "source_library/123_spand/unicode/hi-IN.docx",
             {"category_code": "CAT001", "subject_code": "SUB123", "title_slug": "spand-rahasya",
              "version": "01", "subversion": "02"}),
            ("subjects/unicode-bilingual.json", "mr-IN", "unicode-docx-ingest",
             "library/spand/mr-IN", "source_library/123_spand/unicode/mr-IN.docx",
             {"category_code": "CAT001", "subject_code": "SUB123", "title_slug": "spand-rahasya",
              "version": "03", "subversion": "01"}),
        )
        expected_routes = {
            "local": ("local_source_library", "local_destination_library", "local_destination_library"),
            "r2-output": ("local_source_library", "local_destination_library", "r2_destination_library"),
            "r2": ("r2_source_library", "r2_destination_library", "r2_destination_library"),
        }
        with tempfile.TemporaryDirectory() as directory:
            roots = {"GURUBODH_SOURCE_LIBRARY_ROOT": str(Path(directory) / "source"),
                     "GURUBODH_CMS_LIBRARY_ROOT": str(Path(directory) / "artifacts")}
            environment = fixture("environments/development.json")
            for manifest_file, locale_id, pipeline, subject_dir, source_key, naming in examples:
                manifest = fixture(manifest_file)
                edition = manifest["editions"][locale_id]
                locale = fixture(f"locales/{locale_id}.json")
                self.assertEqual(manifest["artifact_root"] + "/" + locale_id, subject_dir)
                for route_id in ROUTES:
                    route = fixture(f"storage-profiles/{route_id}.json")
                    self.assertEqual(tuple(route[key] for key in ROLE_FIELDS), expected_routes[route_id])
                    for command_id, prepare_job in prepare.items():
                        with self.subTest(manifest=manifest_file, locale=locale_id,
                                          route=route_id, command=command_id):
                            command = fixture(f"commands/{command_id}.json")
                            before = copy.deepcopy((command, route, environment, manifest, locale))
                            for kind, data in (("command-definition", command),
                                               ("storage-profile", route), ("environment", environment)):
                                validate_component(data, kind)
                            job = {"schema_version": command["job_schema_version"],
                                   "pipeline": command["pipeline_by_encoding"][edition["source_document"]["font_encoding"]]
                                   if command_id == "prep-subject" else command["pipeline"]}
                            available_names = dict(manifest["identity"])
                            available_names.update(edition["release"])
                            available_names["language"] = locale_id
                            job["naming"] = {key: available_names[key] for key in command["naming_fields"]}
                            for side in ("source", "destination"):
                                store = environment["stores"][route[command[f"{side}_role"]]]
                                location = {"backend": store["backend"]}
                                if store["backend"] == "local":
                                    location["root_dir"] = roots[store["root_dir"]["$env"]]
                                else:
                                    location.update(bucket=store["bucket"], url_base=store["url_base"])
                                if command_id == "prep-subject" and side == "source":
                                    doc = edition["source_document"]
                                    location.update(font_encoding=doc["font_encoding"], file_format=doc["file_format"])
                                    if store["backend"] == "local":
                                        location["relative_path"] = doc["relative_path"]
                                    else:
                                        location["key"] = store["prefix"] + "/" + doc["relative_path"]
                                else:
                                    location["subject_dir"] = manifest["artifact_root"] + "/" + locale_id
                                    if store["backend"] == "r2":
                                        location["prefix"] = store["prefix"]
                                job[side] = location
                            expected_naming = dict(naming)
                            if command_id != "prep-subject":
                                expected_naming["language"] = locale_id
                            if command_id == "generate-docx":
                                del expected_naming["version"], expected_naming["subversion"]
                            self.assertEqual(job["naming"], expected_naming)
                            self.assertEqual(job["schema_version"], {
                                "prep-subject": "1.5.0", "generate-chunks": "1.2.0", "generate-docx": "1.0.0",
                            }[command_id])
                            self.assertEqual(job["pipeline"], pipeline if command_id == "prep-subject" else command_id)
                            self.assertEqual(job["source"]["backend"], "r2" if route_id == "r2" else "local")
                            self.assertEqual(job["destination"]["backend"], "local" if route_id == "local" else "r2")
                            self.assertEqual(job["destination"]["subject_dir"], subject_dir)
                            if route_id != "local":
                                self.assertEqual(job["destination"]["bucket"], "gurubodh-library-dev")
                                self.assertEqual(job["destination"]["prefix"], "cms_library")
                                self.assertIsNone(job["destination"]["url_base"])
                            else:
                                self.assertEqual(job["destination"]["root_dir"], roots["GURUBODH_CMS_LIBRARY_ROOT"])
                            if command_id == "prep-subject":
                                job["chapter_split"] = copy.deepcopy(edition["chapter_split"])
                                job["metadata_defaults"] = {"language": locale_id, **locale["metadata_defaults"]}
                                # Policy choice is supplied explicitly; this test does not implement precedence.
                                job["proofreading"] = fixture("proofreading/gemini-3.6-flash-v1.json")["proofreading"]
                                if route_id == "r2":
                                    self.assertEqual(job["source"]["key"], source_key)
                                    self.assertEqual(job["source"]["bucket"], "gurubodh-library-dev")
                                else:
                                    self.assertEqual(job["source"]["root_dir"], roots["GURUBODH_SOURCE_LIBRARY_ROOT"])
                            else:
                                self.assertEqual(job["source"]["subject_dir"], subject_dir)
                                if route_id != "r2":
                                    self.assertEqual(job["source"]["root_dir"], roots["GURUBODH_CMS_LIBRARY_ROOT"])
                                else:
                                    self.assertEqual(job["source"]["prefix"], "cms_library")
                            if command_id == "generate-chunks":
                                job["chunking"] = fixture("chunking/bge-m3-semantic-window-v1.json")["chunking"]
                            # S4: exact location and metadata expectations are independent
                            # of the component field construction above, including omissions.
                            expected_destination = (
                                {"backend": "local", "root_dir": str(Path(directory) / "artifacts"),
                                 "subject_dir": subject_dir}
                                if route_id == "local" else
                                {"backend": "r2", "bucket": "gurubodh-library-dev", "prefix": "cms_library",
                                 "subject_dir": subject_dir, "url_base": None}
                            )
                            if command_id == "prep-subject":
                                expected_source = (
                                    {"backend": "r2", "bucket": "gurubodh-library-dev", "key": source_key,
                                     "url_base": None} if route_id == "r2" else
                                    {"backend": "local", "root_dir": str(Path(directory) / "source"),
                                     "relative_path": source_key.removeprefix("source_library/")}
                                )
                                expected_source.update(file_format="docx", font_encoding=(
                                    "aps" if manifest_file == "subjects/aps-hindi.json" else "unicode"))
                                expected_split = (
                                    {"enabled": True, "pattern_type": "literal", "pattern": "प्रबोधन"}
                                    if manifest_file == "subjects/aps-hindi.json" else
                                    {"enabled": True, "pattern_type": "regex", "pattern": "^प्रबोधन",
                                     "flags": ["MULTILINE"]} if locale_id == "hi-IN" else {"enabled": False}
                                )
                                self.assertEqual(job["chapter_split"], expected_split)
                                self.assertEqual(job["metadata_defaults"], {
                                    "language": locale_id, "source_script": "Devanagari",
                                    "output_text_encoding": "UTF-8", "summary_chapter_markers": [
                                        "उपसंहार", "उपसंहारात्मक", "उपसंभारात्मक", "उपसंभारात्त्मक", "उपसंभार",
                                    ],
                                })
                            else:
                                expected_source = (
                                    {"backend": "r2", "bucket": "gurubodh-library-dev", "prefix": "cms_library",
                                     "subject_dir": subject_dir, "url_base": None} if route_id == "r2" else
                                    {"backend": "local", "root_dir": str(Path(directory) / "artifacts"),
                                     "subject_dir": subject_dir}
                                )
                            self.assertEqual(job["source"], expected_source)
                            self.assertEqual(job["destination"], expected_destination)
                            self.assertEqual(set(job), {
                                "schema_version", "pipeline", "source", "destination", "naming",
                            } | ({"chapter_split", "metadata_defaults", "proofreading"}
                                 if command_id == "prep-subject" else {"chunking"}
                                 if command_id == "generate-chunks" else set()))
                            self.assertEqual(prepare_job(job, "s3-contract.json").to_payload(), job)
                            if command_id == "generate-chunks":
                                job["chapters"] = ["001", "012"]
                                self.assertEqual(prepare_job(job).to_payload(), job)
                                for bad in ([], ["001", "001"], ["1"], [1], ["००१"]):
                                    job["chapters"] = bad
                                    with self.assertRaises(ConfigurationError):
                                        prepare_job(job)
                                # Preserve the existing job regex's trailing-newline
                                # behavior. Strict invocation validation belongs to #284.
                                job["chapters"] = ["001\n"]
                                self.assertEqual(prepare_job(job).to_payload(), job)
                            else:
                                job["chapters"] = ["001"]
                                with self.assertRaises(ConfigurationError):
                                    prepare_job(job)
                            self.assertEqual((command, route, environment, manifest, locale), before)


if __name__ == "__main__":
    unittest.main()
