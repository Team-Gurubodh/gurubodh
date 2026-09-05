import json
import unittest
from contextlib import redirect_stderr
from copy import deepcopy
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from gurubodh.canonical_source import safe_relative_path
from gurubodh.cli import main
from gurubodh.config import (
    load_generate_chunks_job,
    load_generate_docx_job,
    load_prep_subject_job,
    prepare_generate_docx_job,
)
from gurubodh.contracts import (
    CandidateManifestBinding,
    ChapterStatus,
    CheckpointArtifactRecord,
    ChunkChapterSummary,
    ChunkGenerationSummary,
    DocxChapterSummary,
    DocxGenerationSummary,
    GenerateChunksJob,
    GenerateDocxJob,
    GenerationStatus,
    PrepCheckpointState,
    PrepJobStatus,
    PrepSubjectJob,
    ProofreadingOutcome,
    ProofreadingStatus,
    PublicationStatus,
)
from gurubodh.errors import (
    ConfigurationError,
    ProcessingError,
    PublicationError,
    SourceValidationError,
    StorageError,
)
from gurubodh.schema_validation import validate_artifact
from gurubodh.storage import upload_r2_file


CLI_ROOT = Path(__file__).parents[1]


class WorkflowContractTests(unittest.TestCase):
    def test_job_conversion_keeps_runtime_values_outside_json_payloads(self):
        cases = (
            ("prep-subject.local.json", load_prep_subject_job, PrepSubjectJob),
            ("generate-chunks.local.json", load_generate_chunks_job, GenerateChunksJob),
            ("generate-docx.local.json", load_generate_docx_job, GenerateDocxJob),
        )
        for filename, loader, expected_type in cases:
            path = next((CLI_ROOT / "jobs").rglob(filename))
            raw = json.loads(path.read_text(encoding="utf-8"))

            with self.subTest(filename=filename):
                prepared = loader(path)
                self.assertIsInstance(prepared, expected_type)
                self.assertEqual(prepared.to_payload(), raw)
                self.assertFalse(
                    {
                        "_locale",
                        "_proofreading_config",
                        "_semantic_chunk_config",
                        "_compiled_pattern",
                    }
                    & set(prepared)
                )
                isolated = prepared.to_payload()
                isolated["pipeline"] = "changed"
                self.assertEqual(prepared["pipeline"], raw["pipeline"])

    def test_candidate_manifest_binding_round_trips_at_the_artifact_boundary(self):
        chapter = {
            "generated_chapter_number": "001",
            "content_key": "content-key",
            "normalized_content_sha256": "a" * 64,
            "metadata_artifact": {
                "backend": "local",
                "path": "chapters/text_and_metadata/chapter.json",
                "url": None,
            },
            "text_artifact": {
                "backend": "local",
                "path": "chapters/text_and_metadata/chapter.txt",
                "url": None,
            },
        }
        second_chapter = deepcopy(chapter)
        second_chapter["generated_chapter_number"] = "002"
        second_chapter["content_key"] = "second-content-key"
        payload = {
            "path": Path("chapters/chapter_content_manifest.json"),
            "sha256": "b" * 64,
            "reference": {
                "backend": "local",
                "path": "chapters/chapter_content_manifest.json",
                "url": None,
            },
            "chapters": [chapter, second_chapter],
            "selected_chapters": [second_chapter, chapter],
        }
        expected = deepcopy(payload)

        binding = CandidateManifestBinding.from_internal_payload(payload)
        payload["chapters"][0]["metadata_artifact"]["path"] = "changed.json"

        self.assertEqual(binding.to_internal_payload(), expected)
        self.assertEqual(
            binding.serialized_binding(),
            {"reference": expected["reference"], "sha256": expected["sha256"]},
        )

    def test_checkpoint_conversion_constrains_states_and_returns_copies(self):
        payload = {
            "replacement_authorized": True,
            "state": "succeeded",
            "publication": {"state": "succeeded", "canonical_manifest": None},
            "chapters": [{"state": "succeeded"}],
        }

        state = PrepCheckpointState.from_payload(payload)

        self.assertIs(state.status, PrepJobStatus.SUCCEEDED)
        self.assertTrue(state.replacement_authorized)
        self.assertIs(state.publication_status, PublicationStatus.SUCCEEDED)
        self.assertIs(ChapterStatus(state["chapters"][0]["state"]), ChapterStatus.SUCCEEDED)
        serialized = state.to_payload()
        serialized["state"] = "failed"
        self.assertIs(state.status, PrepJobStatus.SUCCEEDED)

        invalid = payload | {"state": "unknown"}
        with self.assertRaises(ValueError):
            PrepCheckpointState.from_payload(invalid)

        invalid_authorization = payload | {"replacement_authorized": "yes"}
        with self.assertRaises(TypeError):
            PrepCheckpointState.from_payload(invalid_authorization)

    def test_proofreading_conversion_does_not_consume_the_outcome(self):
        outcome = ProofreadingOutcome(
            chapter_number="001",
            status=ProofreadingStatus.SUCCEEDED,
            correction_count=1,
            request_attempts=2,
            successful_request_attempts=1,
            request_diagnostics=None,
            local_diff_summary={"changed_segments": 1},
            unmodified_source_content_key="before",
            canonical_content_key="after",
            artifacts={"canonical_text": {"backend": "local"}},
            checkpoint_artifacts=(CheckpointArtifactRecord("chapter.txt", "c" * 64),),
        )

        first = outcome.proofreading_payload()
        first["artifacts"].clear()
        second = outcome.proofreading_payload()

        self.assertEqual(second["artifacts"], {"canonical_text": {"backend": "local"}})
        self.assertEqual(outcome.request_attempts, 2)
        self.assertEqual(outcome.checkpoint_artifacts[0].path, "chapter.txt")

    def test_generation_summaries_convert_without_exposing_owned_records(self):
        chunk = ChunkChapterSummary(
            chapter_number="001",
            status=GenerationStatus.SUCCEEDED,
            source_text_filename="chapter.txt",
            source_metadata_filename="chapter.json",
            chunk_filename="chapter.chunks.json",
            source_text_artifact={"backend": "local"},
            source_metadata_artifact={"backend": "local"},
            content_key="content-key",
            normalized_content_sha256="d" * 64,
            chunk_count=2,
            estimated_token_count=10,
            chunk_artifact={"backend": "local"},
            chunk_artifact_sha256="e" * 64,
            source_text_checksum={"value": "f" * 64},
            breakpoint_threshold=0.5,
        )
        chunks = ChunkGenerationSummary(
            source_chapter_count=1,
            processed_chapter_count=1,
            chunk_artifacts_written=1,
            total_chunk_count=2,
            total_estimated_token_count=10,
            chapters=[chunk],
        )
        docx = DocxChapterSummary(
            chapter_number="001",
            content_key="content-key",
            normalized_content_sha256="d" * 64,
            source_text={"sha256": "f" * 64},
            generated_title="chapter title",
            docx_filename="chapter.docx",
            docx_artifact={"backend": "local"},
            docx_sha256="a" * 64,
            status=GenerationStatus.SUCCEEDED,
        )
        documents = DocxGenerationSummary(chapters=[docx])

        chunk_payload = chunks.to_payload()
        docx_payload = documents.to_payload()
        chunk_payload["chapters"][0]["status"] = "failed"
        docx_payload["chapters"][0]["generated_title"] = "changed"

        self.assertIs(chunk.status, GenerationStatus.SUCCEEDED)
        self.assertEqual(docx.generated_title, "chapter title")
        self.assertEqual(documents.processed_chapter_count, 1)

    def test_cli_translates_domain_errors_to_parser_exit(self):
        stderr = StringIO()
        with (
            patch(
                "gurubodh.cli.resolve_project_context",
                side_effect=ConfigurationError("invalid project boundary"),
            ),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            main(["generate-docx", "--config", "missing.json"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("invalid project boundary", stderr.getvalue())

    def test_reusable_services_raise_specific_domain_errors(self):
        with self.assertRaises(ConfigurationError):
            prepare_generate_docx_job({})
        with self.assertRaises(SourceValidationError):
            safe_relative_path("../chapter.txt", "candidate text")
        with self.assertRaises(ProcessingError):
            validate_artifact({}, "chapter content manifest")

        class FailingUploader:
            def upload_file(self, path, bucket, key):
                raise OSError("unavailable")

        with self.assertRaises(StorageError):
            upload_r2_file(
                FailingUploader(),
                {"bucket": "test-bucket"},
                Path("chapter.txt"),
                "subject/chapter.txt",
            )
        self.assertTrue(issubclass(PublicationError, StorageError))


if __name__ == "__main__":
    unittest.main()
