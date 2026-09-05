import tempfile
import unittest
from pathlib import Path

from gurubodh.canonical_release import (
    CHECKPOINT_SCHEMA_VERSION,
    JOB_STATE_RELATIVE_PATH,
)
from gurubodh.contracts import PrepCheckpointState, PrepSubjectJob
from gurubodh.errors import ProcessingError
from gurubodh.locales import locale_spec
from gurubodh.prep_checkpoint import PrepCheckpointManager
from gurubodh.prep_checkpoint_store import (
    LocalCheckpointStore,
    R2CheckpointStore,
    workspace_relative_path,
)
from gurubodh.prep_coordination import (
    LocalAdvisoryCoordinator,
    R2AdvisoryCoordinator,
)
from gurubodh.prep_metrics import PrepMetrics
from gurubodh.prep_publication import LocalPrepPublisher, R2PrepPublisher
from gurubodh.proofreading import ProofreadingSettings
from gurubodh.storage import CANONICAL_ARTIFACT_FILES, PREP_ARTIFACT_DIRS


class FakeR2Client:
    def __init__(self):
        self.objects = {}
        self.uploads = []

    def exists(self, _bucket, key):
        return key in self.objects

    def prefix_has_objects(self, _bucket, prefix):
        return any(key.startswith(prefix) for key in self.objects)

    def list_keys(self, _bucket, prefix):
        return sorted(key for key in self.objects if key.startswith(prefix))

    def download_file(self, _bucket, key, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(self.objects[key])

    def upload_file(self, path, _bucket, key):
        self.uploads.append(key)
        self.objects[key] = Path(path).read_bytes()

    def delete_prefix(self, bucket, prefix):
        return self.delete_keys(
            bucket, [key for key in self.objects if key.startswith(prefix)]
        )

    def delete_keys(self, _bucket, keys):
        deleted = []
        for key in keys:
            if key in self.objects:
                deleted.append(key)
                del self.objects[key]
        return deleted


def prep_job(root: Path, destination: dict | None = None) -> PrepSubjectJob:
    payload = {
        "pipeline": "unicode-docx-ingest",
        "source": {
            "backend": "local",
            "root_dir": str(root),
            "relative_path": "source.docx",
        },
        "destination": destination
        or {
            "backend": "local",
            "root_dir": str(root),
            "subject_dir": "subject/hi-IN",
        },
        "naming": {
            "category_code": "CAT001",
            "subject_code": "SUB123",
            "title_slug": "component-test",
            "version": "01",
            "subversion": "01",
        },
        "chapter_split": {
            "enabled": True,
            "pattern_type": "literal",
            "pattern": "CHAPTER",
        },
        "metadata_defaults": {"language": "hi-IN"},
    }
    return PrepSubjectJob(
        payload,
        locale_spec("hi-IN"),
        ProofreadingSettings(min_request_interval_seconds=0),
    )


def checkpoint_state() -> PrepCheckpointState:
    return PrepCheckpointState.from_payload(
        {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "job_id": "00000000-0000-4000-8000-000000000001",
            "replacement_authorized": True,
            "state": "running",
            "created_at": "2026-09-04T00:00:00Z",
            "updated_at": "2026-09-04T00:00:00Z",
            "run": {},
            "lease": {},
            "compatibility": {
                "fingerprint": "a" * 64,
                "source_docx_sha256": "b" * 64,
                "output_affecting_inputs": {"checkpoint_contract_version": 2},
            },
            "chapters": [],
            "counts": {"succeeded": 0, "failed": 0, "pending": 0},
            "publication": {
                "state": "not_ready",
                "canonical_manifest": None,
            },
            "run_reports": [],
            "workspace": {
                "relative_path": str(
                    workspace_relative_path(
                        "00000000-0000-4000-8000-000000000001"
                    )
                ),
                "status": "active",
            },
            "failure": None,
        }
    )


class CheckpointStoreContractTests(unittest.TestCase):
    def _exercise_store(self, store, recreate):
        state = checkpoint_state()
        workspace = workspace_relative_path(state["job_id"])
        artifact = store.subject_dir / workspace / "chapter.txt"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("checkpoint", encoding="utf-8")

        store.commit(
            state,
            [artifact],
            "checkpoint_chapter_artifacts",
        )
        store.close()

        restored_store = recreate()
        loaded = restored_store.load()
        self.assertEqual(loaded.to_payload(), state.to_payload())
        self.assertTrue(loaded.replacement_authorized)
        restored_store.restore_workspace(workspace)
        restored = restored_store.subject_dir / workspace / "chapter.txt"
        self.assertEqual(restored.read_text(encoding="utf-8"), "checkpoint")
        restored_store.remove_workspace(workspace)
        self.assertFalse(restored.exists())
        restored_store.close()

    def test_local_and_r2_implement_the_same_checkpoint_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local_job = prep_job(root)
            local_metrics = PrepMetrics(False)
            local_factory = lambda: LocalCheckpointStore(
                local_job, local_metrics
            )
            self._exercise_store(local_factory(), local_factory)

            client = FakeR2Client()
            r2_job = prep_job(
                root,
                {
                    "backend": "r2",
                    "bucket": "test-bucket",
                    "prefix": "cms_library",
                    "subject_dir": "subject/hi-IN",
                    "url_base": None,
                },
            )
            r2_metrics = PrepMetrics(True)
            r2_factory = lambda: R2CheckpointStore(
                r2_job, r2_metrics, client
            )
            self._exercise_store(r2_factory(), r2_factory)
            state_key = (
                "cms_library/subject/hi-IN/"
                + JOB_STATE_RELATIVE_PATH.as_posix()
            )
            self.assertNotIn(
                "cms_library/subject/hi-IN/.work/prep-subject/"
                "00000000-0000-4000-8000-000000000001/chapter.txt",
                client.objects,
            )
            self.assertEqual(client.uploads[1], state_key)

    def test_local_and_r2_archive_prior_state_and_detect_prep_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = checkpoint_state()
            workspace = workspace_relative_path(state["job_id"])

            local_store = LocalCheckpointStore(
                prep_job(root), PrepMetrics(False)
            )
            local_workspace_file = (
                local_store.subject_dir / workspace / "discard.txt"
            )
            local_workspace_file.parent.mkdir(parents=True, exist_ok=True)
            local_workspace_file.write_text("discard", encoding="utf-8")
            local_canonical = (
                local_store.subject_dir / CANONICAL_ARTIFACT_FILES[0]
            )
            local_canonical.parent.mkdir(parents=True, exist_ok=True)
            local_canonical.write_text("{}\n", encoding="utf-8")
            self.assertTrue(local_store.prep_artifacts_exist())
            local_store.archive_prior_state(state, workspace)
            self.assertFalse(local_workspace_file.exists())
            self.assertEqual(
                len(
                    list(
                        (
                            local_store.subject_dir
                            / "run_state/prep-subject/archive"
                        ).glob("*-job-state.json")
                    )
                ),
                1,
            )

            client = FakeR2Client()
            r2_job = prep_job(
                root,
                {
                    "backend": "r2",
                    "bucket": "test-bucket",
                    "prefix": "cms_library",
                    "subject_dir": "subject/hi-IN",
                    "url_base": None,
                },
            )
            r2_store = R2CheckpointStore(
                r2_job, PrepMetrics(True), client
            )
            prefix = "cms_library/subject/hi-IN/"
            remote_workspace = prefix + workspace.as_posix() + "/discard.txt"
            client.objects[remote_workspace] = b"discard"
            client.objects[
                prefix + CANONICAL_ARTIFACT_FILES[0].as_posix()
            ] = b"{}\n"
            self.assertTrue(r2_store.prep_artifacts_exist())
            r2_store.archive_prior_state(state, workspace)
            self.assertNotIn(remote_workspace, client.objects)
            self.assertEqual(
                len(
                    [
                        key
                        for key in client.objects
                        if key.startswith(prefix + "run_state/prep-subject/archive/")
                    ]
                ),
                1,
            )
            r2_store.close()

    def test_prior_state_archival_removes_only_its_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            job = prep_job(root)
            store = LocalCheckpointStore(job, PrepMetrics(False))
            state = checkpoint_state()
            workspace = workspace_relative_path(state["job_id"])
            retained = store.subject_dir / "unrelated" / "keep.txt"
            discarded = store.subject_dir / workspace / "discard.txt"
            retained.parent.mkdir(parents=True, exist_ok=True)
            discarded.parent.mkdir(parents=True, exist_ok=True)
            retained.write_text("keep", encoding="utf-8")
            discarded.write_text("discard", encoding="utf-8")

            store.archive_prior_state(state, workspace)

            archives = list(
                (store.subject_dir / "run_state/prep-subject/archive").glob(
                    "*-job-state.json"
                )
            )
            self.assertEqual(len(archives), 1)
            self.assertTrue(retained.is_file())
            self.assertFalse(discarded.exists())


class CheckpointStateTransitionTests(unittest.TestCase):
    def test_state_transitions_run_against_an_in_memory_store(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            class InMemoryStore:
                destination = prep_job(root)["destination"]
                subject_dir = root / "subject" / "hi-IN"
                state_path = subject_dir / JOB_STATE_RELATIVE_PATH
                is_r2 = False
                client = None

                def __init__(self):
                    self.saved = None

                def load(self):
                    return self.saved

                def restore_workspace(self, _relative_path):
                    return None

                def commit(self, state, *_args):
                    self.saved = PrepCheckpointState.from_payload(
                        state.to_payload()
                    )

                def archive_prior_state(self, _state, _workspace_relative):
                    return None

                def prep_artifacts_exist(self):
                    return False

                def discard_workspace_path(self, _relative_path):
                    return None

                def remove_workspace(self, _relative_path):
                    return None

                def close(self):
                    return None

            class NoopPublisher:
                def publish_canonical(self, _workspace, _overwrite):
                    return {}

                def invalidate_chapter_docx(self):
                    return {"invalidated": False}

                def cleanup_legacy_full_subject(self):
                    return {"invalidated": False}

                def invalidate_semantic_artifacts(self):
                    return {"invalidated": False}

            store = InMemoryStore()
            manager = PrepCheckpointManager(
                prep_job(root),
                resume=False,
                overwrite=False,
                store=store,
                coordinator=R2AdvisoryCoordinator(
                    owner_id="test-owner", clock=lambda: 100.0
                ),
                publisher=NoopPublisher(),
                metrics=PrepMetrics(False),
                clock=lambda: 100.0,
            )
            manager.open()
            self.assertEqual(manager.begin("a" * 64), "started")
            self.assertEqual(store.saved["state"], "running")
            self.assertFalse(store.saved.replacement_authorized)
            manager.mark_incomplete()
            self.assertEqual(store.saved["state"], "incomplete")
            manager.close()


class PrepCoordinationTests(unittest.TestCase):
    def test_advisory_lease_is_testable_without_checkpoint_storage(self):
        now = [100.0]
        owner = R2AdvisoryCoordinator(owner_id="owner", clock=lambda: now[0])
        state = checkpoint_state()
        owner.claim(state)
        self.assertTrue(state["lease"]["active"])

        contender = R2AdvisoryCoordinator(
            owner_id="contender", clock=lambda: now[0]
        )
        with self.assertRaises(ProcessingError):
            contender.validate_loaded_state(state)

        now[0] += 121
        contender.validate_loaded_state(state)
        self.assertTrue(owner.release(state))
        self.assertFalse(state["lease"]["active"])

    def test_local_lock_is_testable_without_chapter_processing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            subject = Path(temp_dir) / "subject"
            first = LocalAdvisoryCoordinator(subject, owner_id="first")
            second = LocalAdvisoryCoordinator(subject, owner_id="second")
            first.acquire()
            try:
                with self.assertRaises(ProcessingError):
                    second.acquire()
            finally:
                first.close()
            second.acquire()
            second.close()


class PrepPublicationTests(unittest.TestCase):
    @staticmethod
    def _write_release(workspace: Path) -> None:
        for relative in PREP_ARTIFACT_DIRS:
            path = workspace / relative / "artifact.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(relative.as_posix(), encoding="utf-8")
        manifest = workspace / CANONICAL_ARTIFACT_FILES[0]
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("{}\n", encoding="utf-8")

    def test_local_publication_promotes_manifest_last(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            subject = root / "subject"
            self._write_release(workspace)

            class RecordingPublisher(LocalPrepPublisher):
                def __init__(self, subject_dir):
                    super().__init__(subject_dir)
                    self.promoted = []

                def _replace_path(self, source, target, relative, *args):
                    self.promoted.append(relative)
                    return super()._replace_path(
                        source, target, relative, *args
                    )

            publisher = RecordingPublisher(subject)
            publisher.publish_canonical(workspace, False)

            self.assertEqual(publisher.promoted[-1], CANONICAL_ARTIFACT_FILES[0])
            self.assertTrue(
                (subject / CANONICAL_ARTIFACT_FILES[0]).is_file()
            )

    def test_r2_publication_uploads_manifest_last_and_cleans_separately(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            self._write_release(workspace)
            client = FakeR2Client()
            job = prep_job(
                root,
                {
                    "backend": "r2",
                    "bucket": "test-bucket",
                    "prefix": "cms_library",
                    "subject_dir": "subject/hi-IN",
                    "url_base": None,
                },
            )
            prefix = "cms_library/subject/hi-IN/"
            client.objects[prefix + "chapters/msword/old.docx"] = b"old"
            publisher = R2PrepPublisher(job, client, PrepMetrics(True))

            publisher.publish_canonical(workspace, False)

            self.assertEqual(
                client.uploads[-1],
                prefix + CANONICAL_ARTIFACT_FILES[0].as_posix(),
            )
            self.assertIn(prefix + "chapters/msword/old.docx", client.objects)
            cleanup = publisher.invalidate_chapter_docx()
            self.assertTrue(cleanup["invalidated"])
            self.assertNotIn(prefix + "chapters/msword/old.docx", client.objects)


if __name__ == "__main__":
    unittest.main()
