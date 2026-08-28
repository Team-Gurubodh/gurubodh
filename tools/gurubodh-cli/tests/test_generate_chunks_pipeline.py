import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from gurubodh.config import load_generate_chunks_job
from gurubodh.content_identity import build_content_identity
from gurubodh.ml.semantic_chunking.models import Chunk, ChunkedDocument, text_sha256, whitespace_insensitive_sha256
from gurubodh.naming import chapter_output_filename
from gurubodh.pipelines.generate_chunks import run_generate_chunks_job
from gurubodh.project import ProjectContext


def base_config(root_dir):
    return {
        "schema_version": "1.1.0",
        "pipeline": "generate-chunks",
        "source": {"backend": "local", "root_dir": str(root_dir), "subject_dir": "123_spand_rahasya/hi-IN"},
        "destination": {"backend": "local", "root_dir": str(root_dir), "subject_dir": "123_spand_rahasya/hi-IN"},
        "naming": {
            "category_code": "CAT001", "subject_code": "SUB123", "title_slug": "spand-rahasya",
            "version": "01", "subversion": "01", "language": "hi-IN",
        },
        "chunking": {
            "provider": "semantic-chunking", "model": "BAAI/bge-m3",
            "model_revision": "5617a9f61b028005a4858fdac845db406aefb181",
            "threshold_percentile": 80.0, "min_chars": 600, "window_size": 3, "batch_size": 16,
            "normalize_contextual_vectors": True, "device": None, "local_files_only": False,
        },
    }


def artifact_reference(backend, root, config, filename):
    relative = f"chapters/text_and_metadata/{filename}"
    if backend == "local":
        return {"backend": "local", "path": relative, "url": None}
    return {"backend": "r2", "bucket": "gurubodh-library-dev", "key": f"cms_library/{config['source']['subject_dir']}/{relative}", "url": None}


def metadata_for(config, chapter_number, text, backend="local"):
    text_name = chapter_output_filename(config, chapter_number, ".txt")
    metadata_name = chapter_output_filename(config, chapter_number, ".json")
    return {
        "schema_version": "1.4.0",
        "document": {
            "category_code": config["naming"]["category_code"], "subject_code": config["naming"]["subject_code"],
            "title_slug": config["naming"]["title_slug"], "chapter_number": f"{chapter_number:03d}",
            "version": "v01.01", "language": config["naming"]["language"],
        },
        "storage": {"artifacts": {
            "text": artifact_reference(backend, None, config, text_name),
            "metadata": artifact_reference(backend, None, config, metadata_name),
        }},
        "integrity": {"artifacts": {"text": {
            "algorithm": "sha256", "encoding": "UTF-8", "line_endings": "LF",
            "scope": "artifact-bytes", "value": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }}},
        "content_identity": build_content_identity(
            config["naming"]["category_code"], config["naming"]["subject_code"], config["naming"]["language"], text
        ),
        "files": {"text_filename": text_name, "metadata_filename": metadata_name},
    }


def write_prepared_chapter(root_dir, config, chapter_number=1, text="पहला वाक्य।\n"):
    subject = Path(root_dir) / config["source"]["subject_dir"]
    directory = subject / "chapters" / "text_and_metadata"
    directory.mkdir(parents=True, exist_ok=True)
    metadata = metadata_for(config, chapter_number, text)
    (directory / metadata["files"]["text_filename"]).write_text(text, encoding="utf-8")
    (directory / metadata["files"]["metadata_filename"]).write_text(json.dumps(metadata, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata


def write_candidate_manifest(root_dir, config, chapters):
    subject = Path(root_dir) / config["source"]["subject_dir"]
    payload = {
        "schema_version": 1,
        "identity_contract_version": 1,
        "subject": {
            "category_code": config["naming"]["category_code"], "subject_code": config["naming"]["subject_code"],
            "language": config["naming"]["language"],
        },
        "chapters": [
            {
                "generated_chapter_number": metadata["document"]["chapter_number"],
                "content_key": metadata["content_identity"]["content_key"],
                "normalized_content_sha256": metadata["content_identity"]["normalized_content_sha256"],
                "metadata_artifact": metadata["storage"]["artifacts"]["metadata"],
                "text_artifact": metadata["storage"]["artifacts"]["text"],
            }
            for metadata in chapters
        ],
    }
    path = subject / "chapters" / "chapter_content_manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state_path = subject / "run_state" / "prep-subject" / "job-state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({
        "schema_version": 1,
        "job_id": "test-job",
        "state": "succeeded",
        "publication": {
            "state": "succeeded",
            "canonical_manifest": {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "chapter_numbers": [entry["generated_chapter_number"] for entry in payload["chapters"]],
            },
        },
        "chapters": [
            {
                "chapter_number": entry["generated_chapter_number"],
                "state": "succeeded",
                "proofreading": {"canonical_content_key": entry["content_key"]},
            }
            for entry in payload["chapters"]
        ],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, payload


class FakeSegmenter:
    provider_metadata = {}

    def __init__(self):
        self.calls = 0

    def segment(self, text, source_name=None):
        self.calls += 1
        chunk_text = text.strip()
        chunk = Chunk(
            index=1, text=chunk_text, sentence_count=1, char_count=len(chunk_text),
            estimated_token_count=2, start_sentence=0, end_sentence=0, start_char=0,
            end_char=len(chunk_text), chunk_text_sha256=text_sha256(chunk_text),
        )
        return ChunkedDocument(
            source_name=source_name, provider="semantic-chunking", model_name="BAAI/bge-m3",
            strategy_version="semantic-window-v1", threshold_percentile=80.0, min_chars=600,
            window_size=3, batch_size=16, normalize_contextual_vectors=True, device=None,
            breakpoint_threshold=None, chunks=[chunk], source_text_sha256=whitespace_insensitive_sha256(text),
            concatenated_chunks_sha256=whitespace_insensitive_sha256(chunk_text),
        )


class FakeR2Client:
    def __init__(self, objects):
        self.objects = dict(objects)
        self.downloads, self.uploads, self.deleted_prefixes = [], [], []

    def list_keys(self, bucket, prefix):
        return sorted(key for key in self.objects if key.startswith(prefix))

    def prefix_has_objects(self, bucket, prefix):
        return any(key.startswith(prefix) for key in self.objects)

    def exists(self, bucket, key):
        return key in self.objects

    def download_file(self, bucket, key, path):
        self.downloads.append(key)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(self.objects[key], encoding="utf-8")

    def upload_file(self, path, bucket, key):
        self.uploads.append(key)
        self.objects[key] = Path(path).read_text(encoding="utf-8")

    def delete_prefix(self, bucket, prefix):
        self.deleted_prefixes.append(prefix)
        deleted = [key for key in self.objects if key.startswith(prefix)]
        for key in deleted:
            del self.objects[key]
        return deleted


class GenerateChunksPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.context = ProjectContext(root=Path(self.temp_dir.name), legacy_converter=Path(self.temp_dir.name) / "converter.js")

    def load(self, config):
        path = Path(self.temp_dir.name) / "generate-chunks.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return load_generate_chunks_job(path), path

    def test_manifest_is_authoritative_and_v2_artifacts_have_no_vectors(self):
        config = base_config(self.temp_dir.name)
        listed = write_prepared_chapter(self.temp_dir.name, config, 1)
        write_candidate_manifest(self.temp_dir.name, config, [listed])
        subject = Path(self.temp_dir.name) / config["source"]["subject_dir"]
        extra = subject / "chapters" / "text_and_metadata" / "unlisted.txt"
        extra.write_text("ignored", encoding="utf-8")
        (extra.with_suffix(".json")).write_text("{}", encoding="utf-8")
        review = subject / "chapters" / "proofreading" / "unlisted.proofread.json"
        review.parent.mkdir(parents=True)
        review.write_text("{}", encoding="utf-8")
        unmodified = subject / "chapters" / "unmodified_source_text" / "unlisted_unmodified_source.txt"
        unmodified.parent.mkdir(parents=True)
        unmodified.write_text("ignored", encoding="utf-8")
        loaded, config_path = self.load(config)
        segmenter = FakeSegmenter()

        with redirect_stdout(StringIO()):
            result = run_generate_chunks_job(self.context, loaded, config_path=config_path, segmenter=segmenter, progress=lambda _: None)

        output_dir = subject / "chapters" / "semantic_chunks"
        chunk_path = next(output_dir.glob("*.chunks.json"))
        payload = json.loads(chunk_path.read_text(encoding="utf-8"))
        semantic_manifest = json.loads((output_dir / "semantic_chunks_manifest.json").read_text(encoding="utf-8"))
        audit_path = next((subject / "run_reports" / "generate-chunks").glob("*.json"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        source_manifest_bytes = (subject / "chapters" / "chapter_content_manifest.json").read_bytes()
        rendered = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(segmenter.calls, 1)
        self.assertEqual(result["source_chapter_count"], 1)
        self.assertNotIn("dense_embedding", rendered)
        self.assertNotIn('"embedding"', rendered)
        self.assertNotIn("embedding", json.dumps(semantic_manifest, ensure_ascii=False))
        self.assertNotIn("embedding", json.dumps(audit, ensure_ascii=False))
        self.assertEqual(payload["source_references"]["candidate_manifest"]["sha256"], hashlib.sha256(source_manifest_bytes).hexdigest())
        self.assertEqual(semantic_manifest["source_candidate_manifest"]["sha256"], hashlib.sha256(source_manifest_bytes).hexdigest())
        self.assertEqual(semantic_manifest["chapters"][0]["chunk_artifact_sha256"], hashlib.sha256(chunk_path.read_bytes()).hexdigest())
        self.assertIn("chunking_config_key", semantic_manifest["chunking"])
        self.assertEqual(payload["chunks"][0]["estimated_token_count"], 2)

    def test_succeeded_old_contract_release_with_legacy_metadata_remains_consumable(self):
        config = base_config(self.temp_dir.name)
        metadata = write_prepared_chapter(self.temp_dir.name, config, 1)
        subject = Path(self.temp_dir.name) / config["source"]["subject_dir"]
        metadata_path = subject / "chapters" / "text_and_metadata" / metadata["files"]["metadata_filename"]
        legacy_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        legacy_metadata["schema_version"] = "1.3.0"
        legacy_metadata["files"]["msword_filename"] = "legacy.docx"
        legacy_metadata["storage"]["artifacts"].update(
            {
                "msword": {"backend": "local", "path": "chapters/msword/legacy.docx", "url": None},
                "full_subject_msword": {"backend": "local", "path": "full_subject/legacy.docx", "url": None},
                "full_subject_text": {"backend": "local", "path": "full_subject/legacy.txt", "url": None},
            }
        )
        metadata_path.write_text(json.dumps(legacy_metadata, ensure_ascii=False) + "\n", encoding="utf-8")
        write_candidate_manifest(self.temp_dir.name, config, [metadata])
        loaded, config_path = self.load(config)
        segmenter = FakeSegmenter()

        with redirect_stdout(StringIO()):
            result = run_generate_chunks_job(
                self.context,
                loaded,
                config_path=config_path,
                segmenter=segmenter,
                progress=lambda _: None,
            )

        self.assertEqual(result["processed_chapter_count"], 1)
        self.assertEqual(segmenter.calls, 1)

    def test_invalid_manifest_references_fail_before_segmenting(self):
        config = base_config(self.temp_dir.name)
        metadata = write_prepared_chapter(self.temp_dir.name, config, 1)
        manifest_path, manifest = write_candidate_manifest(self.temp_dir.name, config, [metadata])
        manifest["chapters"][0]["text_artifact"]["path"] = "../escaped.txt"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        loaded, config_path = self.load(config)
        segmenter = FakeSegmenter()

        with self.assertRaisesRegex(SystemExit, "must not escape"):
            run_generate_chunks_job(self.context, loaded, config_path=config_path, segmenter=segmenter, progress=lambda _: None)
        self.assertEqual(segmenter.calls, 0)

    def test_manifest_identity_mismatch_fails_before_segmenting(self):
        config = base_config(self.temp_dir.name)
        metadata = write_prepared_chapter(self.temp_dir.name, config, 1)
        manifest_path, manifest = write_candidate_manifest(self.temp_dir.name, config, [metadata])
        manifest["chapters"][0]["content_key"] = "00000000-0000-5000-8000-000000000000"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        loaded, config_path = self.load(config)
        segmenter = FakeSegmenter()

        with self.assertRaisesRegex(SystemExit, "content identity disagree"):
            run_generate_chunks_job(self.context, loaded, config_path=config_path, segmenter=segmenter, progress=lambda _: None)
        self.assertEqual(segmenter.calls, 0)

    def test_cr_bearing_text_claiming_lf_is_rejected_before_segmenting(self):
        config = base_config(self.temp_dir.name)
        metadata = write_prepared_chapter(self.temp_dir.name, config, 1)
        write_candidate_manifest(self.temp_dir.name, config, [metadata])
        subject = Path(self.temp_dir.name) / config["source"]["subject_dir"]
        text_path = subject / "chapters" / "text_and_metadata" / metadata["files"]["text_filename"]
        text_path.write_bytes("पहला\r\nदूसरा\n".encode("utf-8"))
        metadata_path = subject / "chapters" / "text_and_metadata" / metadata["files"]["metadata_filename"]
        updated_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        updated_metadata["integrity"]["artifacts"]["text"]["value"] = hashlib.sha256(text_path.read_bytes()).hexdigest()
        metadata_path.write_text(json.dumps(updated_metadata, ensure_ascii=False) + "\n", encoding="utf-8")
        loaded, config_path = self.load(config)
        segmenter = FakeSegmenter()

        with self.assertRaisesRegex(SystemExit, "source text checksum does not match metadata"):
            run_generate_chunks_job(self.context, loaded, config_path=config_path, segmenter=segmenter, progress=lambda _: None)
        self.assertEqual(segmenter.calls, 0)

    def test_chapter_filter_uses_manifest_and_reports_absent_number(self):
        config = base_config(self.temp_dir.name)
        first = write_prepared_chapter(self.temp_dir.name, config, 1)
        second = write_prepared_chapter(self.temp_dir.name, config, 2, "दूसरा वाक्य।\n")
        write_candidate_manifest(self.temp_dir.name, config, [first, second])
        config["chapters"] = ["002"]
        loaded, config_path = self.load(config)
        with redirect_stdout(StringIO()):
            result = run_generate_chunks_job(self.context, loaded, config_path=config_path, segmenter=FakeSegmenter(), progress=lambda _: None)
        self.assertEqual(result["processed_chapter_count"], 1)
        self.assertEqual(result["skipped_chapter_count"], 1)
        self.assertEqual(len(list((Path(self.temp_dir.name) / config["source"]["subject_dir"] / "chapters" / "semantic_chunks").glob("*.chunks.json"))), 1)

        config["chapters"] = ["003"]
        loaded, config_path = self.load(config)
        with self.assertRaisesRegex(SystemExit, "absent from the candidate manifest"):
            run_generate_chunks_job(self.context, loaded, config_path=config_path, segmenter=FakeSegmenter(), progress=lambda _: None)

    def test_legacy_output_requires_overwrite_and_is_removed(self):
        config = base_config(self.temp_dir.name)
        metadata = write_prepared_chapter(self.temp_dir.name, config, 1)
        write_candidate_manifest(self.temp_dir.name, config, [metadata])
        subject = Path(self.temp_dir.name) / config["source"]["subject_dir"]
        legacy = subject / "chapters" / "semantic_chunks_and_embeddings"
        legacy.mkdir()
        (legacy / "old.chunks.json").write_text("{}", encoding="utf-8")
        loaded, config_path = self.load(config)
        with self.assertRaisesRegex(SystemExit, "Legacy combined"):
            run_generate_chunks_job(self.context, loaded, config_path=config_path, segmenter=FakeSegmenter(), progress=lambda _: None)
        with redirect_stdout(StringIO()):
            run_generate_chunks_job(self.context, loaded, overwrite=True, config_path=config_path, segmenter=FakeSegmenter(), progress=lambda _: None)
        self.assertFalse(legacy.exists())

    def test_incomplete_prep_state_refuses_before_overwrite_can_delete_existing_chunks(self):
        config = base_config(self.temp_dir.name)
        metadata = write_prepared_chapter(self.temp_dir.name, config, 1)
        write_candidate_manifest(self.temp_dir.name, config, [metadata])
        subject = Path(self.temp_dir.name) / config["source"]["subject_dir"]
        state_path = subject / "run_state" / "prep-subject" / "job-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["state"] = "publishing"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        previous = subject / "chapters" / "semantic_chunks" / "previous.chunks.json"
        previous.parent.mkdir(parents=True)
        previous.write_text("previous", encoding="utf-8")
        loaded, config_path = self.load(config)

        with self.assertRaisesRegex(SystemExit, "latest prep-subject job is not succeeded"):
            run_generate_chunks_job(self.context, loaded, overwrite=True, config_path=config_path, segmenter=FakeSegmenter(), progress=lambda _: None)
        self.assertTrue(previous.is_file())

    def test_r2_materializes_only_selected_manifest_artifacts(self):
        config = base_config(self.temp_dir.name)
        config["source"] = {"backend": "r2", "bucket": "gurubodh-library-dev", "prefix": "cms_library", "subject_dir": "123_spand_rahasya/hi-IN", "url_base": None}
        config["destination"] = dict(config["source"])
        text_one, text_two = "पहला।\n", "दूसरा।\n"
        metadata_one = metadata_for(config, 1, text_one, "r2")
        metadata_two = metadata_for(config, 2, text_two, "r2")
        manifest = {
            "schema_version": 1, "identity_contract_version": 1,
            "subject": {"category_code": "CAT001", "subject_code": "SUB123", "language": "hi-IN"},
            "chapters": [
                {"generated_chapter_number": metadata_one["document"]["chapter_number"], "content_key": metadata_one["content_identity"]["content_key"], "normalized_content_sha256": metadata_one["content_identity"]["normalized_content_sha256"], "metadata_artifact": metadata_one["storage"]["artifacts"]["metadata"], "text_artifact": metadata_one["storage"]["artifacts"]["text"]},
                {"generated_chapter_number": metadata_two["document"]["chapter_number"], "content_key": metadata_two["content_identity"]["content_key"], "normalized_content_sha256": metadata_two["content_identity"]["normalized_content_sha256"], "metadata_artifact": metadata_two["storage"]["artifacts"]["metadata"], "text_artifact": metadata_two["storage"]["artifacts"]["text"]},
            ],
        }
        prefix = "cms_library/123_spand_rahasya/hi-IN/chapters"
        client = FakeR2Client({
            f"{prefix}/chapter_content_manifest.json": json.dumps(manifest, ensure_ascii=False),
            metadata_one["storage"]["artifacts"]["metadata"]["key"]: json.dumps(metadata_one, ensure_ascii=False),
            metadata_one["storage"]["artifacts"]["text"]["key"]: text_one,
            metadata_two["storage"]["artifacts"]["metadata"]["key"]: json.dumps(metadata_two, ensure_ascii=False),
            metadata_two["storage"]["artifacts"]["text"]["key"]: text_two,
            "cms_library/123_spand_rahasya/hi-IN/chapters/text_and_metadata/unlisted.txt": "ignored",
            "cms_library/123_spand_rahasya/hi-IN/chapters/unmodified_source_text/unlisted_unmodified_source.txt": "ignored",
            "cms_library/123_spand_rahasya/hi-IN/chapters/proofreading/unlisted.proofread.json": "{}",
            "cms_library/123_spand_rahasya/hi-IN/run_state/prep-subject/job-state.json": json.dumps({
                "schema_version": 1,
                "job_id": "test-job",
                "state": "succeeded",
                "publication": {
                    "state": "succeeded",
                    "canonical_manifest": {
                        "sha256": hashlib.sha256(json.dumps(manifest, ensure_ascii=False).encode("utf-8")).hexdigest(),
                        "chapter_numbers": ["001", "002"],
                    },
                },
                "chapters": [
                    {"chapter_number": "001", "state": "succeeded", "proofreading": {"canonical_content_key": metadata_one["content_identity"]["content_key"]}},
                    {"chapter_number": "002", "state": "succeeded", "proofreading": {"canonical_content_key": metadata_two["content_identity"]["content_key"]}},
                ],
            }, ensure_ascii=False),
        })
        config["chapters"] = ["002"]
        loaded, config_path = self.load(config)
        with redirect_stdout(StringIO()):
            run_generate_chunks_job(self.context, loaded, config_path=config_path, segmenter=FakeSegmenter(), r2_client=client, progress=lambda _: None)
        self.assertEqual(client.downloads, [
            f"{prefix}/chapter_content_manifest.json",
            metadata_two["storage"]["artifacts"]["metadata"]["key"],
            metadata_two["storage"]["artifacts"]["text"]["key"],
            "cms_library/123_spand_rahasya/hi-IN/run_state/prep-subject/job-state.json",
        ])
        self.assertTrue(any("/chapters/semantic_chunks/" in key for key in client.uploads))


if __name__ == "__main__":
    unittest.main()
