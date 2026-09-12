import io
import os
import unittest
from unittest.mock import patch

from gurubodh.contracts import (
    ChunkGenerationSummary,
    DocxGenerationSummary,
)
from gurubodh.presentation import (
    CommandPresentation,
    present_derived_summary,
    present_lab_summary,
    present_prep_summary,
)


def prep_metrics(*, completed=0, request_failures=0, checkpoint=(0, 0), canonical=(0, 0)):
    checkpoint_names = (
        "checkpoint_source_snapshots",
        "checkpoint_chapter_artifacts",
        "checkpoint_state_commits",
        "checkpoint_state_archives",
    )
    breakdown = {
        name: {
            "attempts_total": checkpoint[0] + checkpoint[1] if index == 0 else 0,
            "attempts_succeeded": checkpoint[0] if index == 0 else 0,
            "attempts_failed": checkpoint[1] if index == 0 else 0,
        }
        for index, name in enumerate(checkpoint_names)
    }
    breakdown["canonical_publication_artifacts"] = {
        "attempts_total": canonical[0] + canonical[1],
        "attempts_succeeded": canonical[0],
        "attempts_failed": canonical[1],
    }
    return {
        "gemini_generate_content_requests": {
            "attempts_total": completed + request_failures,
            "attempts_succeeded": completed,
            "attempts_failed": request_failures,
        },
        "r2_object_upload_requests": {
            "attempts_total": sum(v["attempts_total"] for v in breakdown.values()),
            "attempts_succeeded": sum(
                v["attempts_succeeded"] for v in breakdown.values()
            ),
            "attempts_failed": sum(v["attempts_failed"] for v in breakdown.values()),
            "breakdown": breakdown,
        },
    }


class TtyBuffer(io.StringIO):
    def isatty(self):
        return True


class PresentationTests(unittest.TestCase):
    def test_color_is_restrained_to_outcomes_and_immediate_failures_on_tty(self):
        output = TtyBuffer()
        with patch.dict(os.environ, {}, clear=True), patch(
            "gurubodh.presentation.sys.stdout", output
        ):
            presentation = CommandPresentation("generate-chunks")
            presentation.stage("processing", "working")
            presentation.failure("generation", ValueError("bad chapter"))
            presentation.summary(
                "succeeded", "1 chapter processed", ["Chunk generation: 1 chapter succeeded, 0 failed."]
            )

        lines = output.getvalue().splitlines()
        self.assertEqual(lines[0], "[generate-chunks processing] working")
        self.assertEqual(
            lines[1],
            "\033[31m[generate-chunks generation] failed: bad chapter\033[0m",
        )
        self.assertEqual(
            lines[2],
            "\033[32mgenerate-chunks: succeeded — 1 chapter processed\033[0m",
        )
        self.assertNotIn("\033[", lines[3])

    def test_non_tty_and_no_color_output_are_plain(self):
        for output, environment in (
            (io.StringIO(), {}),
            (TtyBuffer(), {"NO_COLOR": "1"}),
        ):
            with self.subTest(tty=output.isatty(), no_color=bool(environment)):
                with patch.dict(os.environ, environment, clear=True), patch(
                    "gurubodh.presentation.sys.stdout", output
                ):
                    presentation = CommandPresentation("prep-subject")
                    presentation.failure("proofreading", ValueError("invalid response"))
                    presentation.summary("incomplete", "1 chapter failed", [])
                self.assertNotIn("\033[", output.getvalue())

    def test_prep_summary_separates_validation_requests_uploads_and_publication(self):
        messages = []
        present_prep_summary(
            CommandPresentation("prep-subject", messages.append),
            outcome="incomplete",
            state={
                "counts": {"succeeded": 2, "failed": 1, "pending": 1},
                "publication": {"state": "not_ready"},
            },
            metrics=prep_metrics(completed=3, checkpoint=(19, 0)),
            reused_count=1,
            report_references=None,
            failure_stage="proofreading",
        )

        self.assertEqual(messages[0], "prep-subject: incomplete — 1 chapter failed")
        self.assertIn("Proofreading: 2 chapters succeeded, 1 failed.", messages)
        self.assertIn("Reused: 1 successful chapter checkpoint.", messages)
        self.assertIn("Pending/not attempted: 1 chapter.", messages)
        self.assertIn("Gemini requests: 3 completed, 0 request failures.", messages)
        self.assertIn(
            "R2 upload operations: 19 succeeded, 0 failed (checkpoint data; excludes audit reports).",
            messages,
        )
        self.assertIn(
            "Final publication: not performed; preparation incomplete.", messages
        )

    def test_derived_summaries_cover_skipped_pending_and_unknown_counts(self):
        chunk_messages = []
        chunks = ChunkGenerationSummary(
            source_chapter_count=5,
            processed_chapter_count=2,
            skipped_chapter_count=1,
            failed_chapter_count=1,
        )
        present_derived_summary(
            CommandPresentation("generate-chunks", chunk_messages.append),
            outcome="failed",
            generation=chunks,
            source_count=5,
            publication={"status": "not_started", "backend": "local"},
            report_references=None,
            failure_stage="generation",
        )
        self.assertIn("Chunk generation: 2 chapters succeeded, 1 failed.", chunk_messages)
        self.assertIn("Skipped: 1 chapter not selected.", chunk_messages)
        self.assertIn("Pending/not attempted: 1 chapter.", chunk_messages)

        docx_messages = []
        present_derived_summary(
            CommandPresentation("generate-docx", docx_messages.append),
            outcome="failed",
            generation=DocxGenerationSummary(),
            source_count=None,
            publication={"status": "not_started", "backend": "local"},
            report_references=None,
            failure_stage="source_validation",
        )
        self.assertIn(
            "DOCX generation: counts unavailable; source validation did not complete.",
            docx_messages,
        )

    def test_lab_summary_reports_completed_request_without_claiming_failed_output(self):
        messages = []
        error = RuntimeError("invalid response")
        error.request_attempts = 1
        error.successful_request_attempts = 1
        present_lab_summary(
            CommandPresentation("lab proofread", messages.append),
            outcome="failed",
            failure_stage="proofreading",
            source_validated=True,
            proofreading_succeeded=False,
            response=None,
            error=error,
            run_directory="/tmp/failed-run",
            report_reference=None,
            output_available=False,
        )
        self.assertIn("Gemini requests: 1 completed, 0 request failures.", messages)
        self.assertIn(
            "Local output: not available; the lab run did not complete.", messages
        )
        self.assertFalse(any(line.startswith("Output:") for line in messages))


if __name__ == "__main__":
    unittest.main()
