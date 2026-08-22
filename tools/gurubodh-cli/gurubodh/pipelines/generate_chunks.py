"""Candidate-manifest-bound semantic chunk generation."""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from gurubodh.content_identity import validate_content_identity
from gurubodh.constants import (
    ENTRY_POINT_GENERATE_CHUNKS,
    SEMANTIC_CHUNKS_ARTIFACT_SCHEMA_VERSION,
    SEMANTIC_CHUNKS_MANIFEST_SCHEMA_VERSION,
    SEMANTIC_CHUNKS_OUTPUT_DIR,
)
from gurubodh.generate_chunks_audit import GenerateChunksAuditWriter
from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig
from gurubodh.ml.semantic_chunking.file_io import validate_document_for_source
from gurubodh.ml.semantic_chunking.segmenter import ParagraphSegmenter, SemanticChunkingParagraphSegmenter
from gurubodh.naming import chapter_chunks_output_filename
from gurubodh.storage import (
    CHUNKS_REPORT_DIR,
    R2StorageClient,
    destination_artifact_reference,
    is_local,
    is_r2,
    optional_url,
    r2_existing_artifacts_error,
    subject_artifact_object_key,
    subject_artifact_prefix,
    upload_r2_file,
)


TEXT_AND_METADATA_RELATIVE_DIR = Path("chapters") / "text_and_metadata"
CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH = Path("chapters") / "chapter_content_manifest.json"
SEMANTIC_CHUNKS_RELATIVE_DIR = Path("chapters") / SEMANTIC_CHUNKS_OUTPUT_DIR
LEGACY_SEMANTIC_CHUNKS_RELATIVE_DIR = Path("chapters") / "semantic_chunks_and_embeddings"


def run_generate_chunks_job(
    context, config, entry_point=ENTRY_POINT_GENERATE_CHUNKS, overwrite=False,
    config_path=None, segmenter: ParagraphSegmenter | None = None, r2_client=None, progress=print,
):
    semantic_config = config["_semantic_chunk_config"]
    client = r2_client if (is_r2(config["source"]) or is_r2(config["destination"])) else None
    if client is None and (is_r2(config["source"]) or is_r2(config["destination"])):
        client = R2StorageClient.from_env()
    job = prepare_generate_chunks_job(config, overwrite, r2_client=client, progress=progress)
    try:
        # Every source check completed before the lazy segmenter can load a model.
        segmenter = segmenter or SemanticChunkingParagraphSegmenter(semantic_config, progress=progress)
        result = write_chunk_artifacts(config, job, semantic_config, segmenter, progress=progress)
        audit = GenerateChunksAuditWriter(context, config_path, config, entry_point, overwrite, job, result)
        result["audit_report_references"] = audit_report_references(config, audit.paths)
        write_chunk_manifest(job["paths"]["chunk_manifest"], config, job, semantic_config, result)
        progress("[manifest] wrote semantic_chunks_manifest.json")
        if is_r2(config["destination"]):
            audit.write_r2_pending()
            publish_generate_chunks_r2(config, job, overwrite, r2_client=client, before_upload=audit.before_r2_upload)
            audit.announce_locations()
        else:
            audit.write_local_success()
        return result
    finally:
        cleanup_job(job)


def prepare_generate_chunks_job(config, overwrite, r2_client=None, progress=print):
    source_subject, source_temp_dir, candidate_manifest = materialize_source_subject(config, r2_client, progress)
    candidate_sources = validate_materialized_candidates(config, source_subject, candidate_manifest)
    destination_subject, destination_temp_dir = destination_subject_dir(config)
    preflight = ensure_destination_available(config, destination_subject, overwrite, r2_client)
    paths = {
        "source_subject": source_subject,
        "source_text_and_metadata": source_subject / TEXT_AND_METADATA_RELATIVE_DIR,
        "candidate_manifest": source_subject / CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH,
        "destination_subject": destination_subject,
        "semantic_chunks": destination_subject / SEMANTIC_CHUNKS_RELATIVE_DIR,
        "chunk_manifest": destination_subject / SEMANTIC_CHUNKS_RELATIVE_DIR / "semantic_chunks_manifest.json",
    }
    paths["semantic_chunks"].mkdir(parents=True, exist_ok=True)
    return {
        "paths": paths, "candidate_sources": candidate_sources, "candidate_manifest": candidate_manifest,
        "source_temp_dir": source_temp_dir, "destination_temp_dir": destination_temp_dir,
        "destination_preflight": preflight, "destination_output_prefix": destination_output_prefix(config),
    }


def materialize_source_subject(config, r2_client=None, progress=print):
    """Read the source manifest, then only selected manifest-referenced files."""
    source = config["source"]
    if is_local(source):
        subject_dir = Path(source["root_dir"]).expanduser() / source["subject_dir"]
        if not subject_dir.is_dir():
            raise SystemExit(f"Configured source subject directory does not exist: {subject_dir}")
        manifest = read_candidate_manifest(config, subject_dir / CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH)
        return subject_dir, None, manifest

    temp_dir = tempfile.TemporaryDirectory(prefix="gurubodh-generate-chunks-source-")
    subject_dir = Path(temp_dir.name) / source["subject_dir"]
    client = r2_client or R2StorageClient.from_env()
    manifest_key = subject_artifact_object_key(source, CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH)
    manifest_path = subject_dir / CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH
    progress("Reading candidate chapter manifest from:")
    progress(f"  r2://{source['bucket']}/{manifest_key}")
    try:
        client.download_file(source["bucket"], manifest_key, manifest_path)
        manifest = read_candidate_manifest(config, manifest_path)
        selected = manifest["selected_chapters"]
        width = max(2, len(str(len(selected))))
        for index, candidate in enumerate(selected, start=1):
            for kind in ("metadata", "text"):
                relative_path, key = artifact_relative_path(source, candidate[f"{kind}_artifact"], kind)
                client.download_file(source["bucket"], key, subject_dir / relative_path)
            progress(f"[{index:0{width}d}/{len(selected):0{width}d}] chapter {candidate['generated_chapter_number']} (metadata, text)")
    except SystemExit:
        temp_dir.cleanup()
        raise
    except Exception as exc:
        temp_dir.cleanup()
        raise SystemExit(f"R2 source materialization failed: {exc}") from exc
    return subject_dir, temp_dir, manifest


def read_candidate_manifest(config, manifest_path):
    try:
        raw = Path(manifest_path).read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Candidate chapter manifest is missing or malformed: {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise SystemExit("Candidate chapter manifest must be a JSON object.")
    if manifest.get("schema_version") != 1:
        raise SystemExit("Unsupported candidate chapter manifest schema_version; expected 1.")
    if manifest.get("identity_contract_version") != 1:
        raise SystemExit("Unsupported candidate chapter manifest identity_contract_version; expected 1.")
    expected_subject = {
        "category_code": config["naming"]["category_code"],
        "subject_code": config["naming"]["subject_code"],
        "language": config["naming"]["language"],
    }
    if manifest.get("subject") != expected_subject:
        raise SystemExit("Candidate chapter manifest subject identity does not match the generate-chunks job configuration.")
    entries = manifest.get("chapters")
    if not isinstance(entries, list) or not entries:
        raise SystemExit("Candidate chapter manifest must contain a non-empty chapters array.")
    candidates, numbers = [], set()
    for entry in entries:
        number = entry.get("generated_chapter_number") if isinstance(entry, dict) else None
        if not isinstance(number, str) or len(number) != 3 or not number.isdigit():
            raise SystemExit("Candidate chapter manifest has an invalid generated_chapter_number.")
        if number in numbers:
            raise SystemExit(f"Candidate chapter manifest contains duplicate chapter number: {number}")
        numbers.add(number)
        if not isinstance(entry.get("content_key"), str) or not isinstance(entry.get("normalized_content_sha256"), str):
            raise SystemExit(f"Candidate chapter manifest entry {number} is missing content identity fields.")
        metadata_artifact, text_artifact = entry.get("metadata_artifact"), entry.get("text_artifact")
        artifact_relative_path(config["source"], metadata_artifact, "metadata")
        artifact_relative_path(config["source"], text_artifact, "text")
        candidates.append({
            "generated_chapter_number": number, "content_key": entry["content_key"],
            "normalized_content_sha256": entry["normalized_content_sha256"],
            "metadata_artifact": metadata_artifact, "text_artifact": text_artifact,
        })
    requested = set(config.get("chapters") or [])
    missing = sorted(requested - numbers)
    if missing:
        raise SystemExit(f"Requested chapter number(s) are absent from the candidate manifest: {', '.join(missing)}")
    return {
        "path": Path(manifest_path), "sha256": hashlib.sha256(raw).hexdigest(),
        "reference": source_manifest_reference(config), "chapters": candidates,
        "selected_chapters": [candidate for candidate in candidates if not requested or candidate["generated_chapter_number"] in requested],
    }


def safe_relative_path(value, context):
    if not isinstance(value, str) or not value or "\\" in value:
        raise SystemExit(f"{context} must be a non-empty POSIX relative path.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise SystemExit(f"{context} must not escape the subject artifact tree.")
    return Path(*path.parts)


def artifact_relative_path(source, reference, kind):
    if not isinstance(reference, dict):
        raise SystemExit(f"Candidate manifest {kind}_artifact must be an object.")
    suffix = ".json" if kind == "metadata" else ".txt"
    if is_local(source):
        if reference.get("backend") != "local" or not isinstance(reference.get("path"), str) or "url" not in reference:
            raise SystemExit(f"Candidate manifest {kind}_artifact must be a local storage reference.")
        relative_path = safe_relative_path(reference["path"], f"candidate manifest {kind}_artifact.path")
        if relative_path.parent != TEXT_AND_METADATA_RELATIVE_DIR or relative_path.suffix != suffix:
            raise SystemExit(f"Candidate manifest {kind}_artifact must reference chapters/text_and_metadata/*{suffix}.")
        return relative_path, None
    if reference.get("backend") != "r2" or reference.get("bucket") != source["bucket"] or not isinstance(reference.get("key"), str) or "url" not in reference:
        raise SystemExit(f"Candidate manifest {kind}_artifact must be an R2 reference in the configured source bucket.")
    key, prefix = reference["key"], subject_artifact_prefix(source)
    if not key.startswith(prefix):
        raise SystemExit(f"Candidate manifest {kind}_artifact escapes the configured source subject prefix.")
    relative_path = safe_relative_path(key.removeprefix(prefix), f"candidate manifest {kind}_artifact.key")
    if key != subject_artifact_object_key(source, relative_path) or relative_path.parent != TEXT_AND_METADATA_RELATIVE_DIR or relative_path.suffix != suffix:
        raise SystemExit(f"Candidate manifest {kind}_artifact must reference chapters/text_and_metadata/*{suffix}.")
    return relative_path, key


def source_manifest_reference(config):
    source = config["source"]
    if is_local(source):
        return {"backend": "local", "path": str(CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH), "url": None}
    key = subject_artifact_object_key(source, CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH)
    return {"backend": "r2", "bucket": source["bucket"], "key": key, "url": optional_url(source.get("url_base"), key)}


def subject_artifact_path(subject_dir, relative_path, context):
    root = Path(subject_dir).resolve()
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root):
        raise SystemExit(f"{context} escapes the source subject artifact tree.")
    return target


def validate_materialized_candidates(config, source_subject, candidate_manifest):
    """Verify every selected manifest entry, its metadata, and its text."""
    sources = []
    expected_subject = {
        "category_code": config["naming"]["category_code"],
        "subject_code": config["naming"]["subject_code"],
        "language": config["naming"]["language"],
    }
    for candidate in candidate_manifest["selected_chapters"]:
        metadata_relative, _ = artifact_relative_path(config["source"], candidate["metadata_artifact"], "metadata")
        text_relative, _ = artifact_relative_path(config["source"], candidate["text_artifact"], "text")
        metadata_path = subject_artifact_path(source_subject, metadata_relative, "Candidate metadata artifact")
        text_path = subject_artifact_path(source_subject, text_relative, "Candidate text artifact")
        if not metadata_path.is_file() or not text_path.is_file():
            raise SystemExit(f"Candidate chapter {candidate['generated_chapter_number']} has a missing manifest-referenced artifact.")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            text_bytes, text = text_path.read_bytes(), text_path.read_text(encoding="utf-8")
            document = metadata["document"]
            storage = metadata["storage"]["artifacts"]
            integrity = metadata["integrity"]["artifacts"]["text"]
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise SystemExit(f"Candidate chapter {candidate['generated_chapter_number']} has malformed prepared metadata or text: {exc}") from exc
        if {key: document.get(key) for key in expected_subject} != expected_subject:
            raise SystemExit(f"Candidate chapter {candidate['generated_chapter_number']} metadata subject identity does not match the job.")
        if document.get("chapter_number") != candidate["generated_chapter_number"]:
            raise SystemExit(f"Candidate manifest and metadata disagree on chapter number for {candidate['generated_chapter_number']}.")
        files = metadata.get("files", {})
        if files.get("metadata_filename") != metadata_path.name or files.get("text_filename") != text_path.name:
            raise SystemExit(f"Candidate chapter {candidate['generated_chapter_number']} metadata filenames disagree with manifest references.")
        if storage.get("metadata") != candidate["metadata_artifact"] or storage.get("text") != candidate["text_artifact"]:
            raise SystemExit(f"Candidate chapter {candidate['generated_chapter_number']} metadata storage references disagree with the manifest.")
        if not isinstance(integrity, dict) or integrity.get("value") != hashlib.sha256(text_bytes).hexdigest():
            raise SystemExit(f"Candidate chapter {candidate['generated_chapter_number']} source text checksum does not match metadata.")
        try:
            identity = validate_content_identity(metadata.get("content_identity"), document["category_code"], document["subject_code"], document["language"], text)
        except (KeyError, ValueError) as exc:
            raise SystemExit(f"Prepared chapter {metadata_path} has missing or invalid content_identity: {exc}") from exc
        if identity["content_key"] != candidate["content_key"] or identity["normalized_content_sha256"] != candidate["normalized_content_sha256"]:
            raise SystemExit(f"Candidate manifest and metadata content identity disagree for chapter {candidate['generated_chapter_number']}.")
        sources.append({"chapter_number": candidate["generated_chapter_number"], "text_path": text_path, "metadata_path": metadata_path, "metadata": metadata})
    return sources


def destination_subject_dir(config):
    destination = config["destination"]
    if is_local(destination):
        return Path(destination["root_dir"]).expanduser() / destination["subject_dir"], None
    temp_dir = tempfile.TemporaryDirectory(prefix="gurubodh-generate-chunks-output-")
    return Path(temp_dir.name) / destination["subject_dir"], temp_dir


def destination_output_prefix(config):
    return subject_artifact_object_key(config["destination"], SEMANTIC_CHUNKS_RELATIVE_DIR) + "/" if is_r2(config["destination"]) else None


def legacy_output_prefix(config):
    return subject_artifact_object_key(config["destination"], LEGACY_SEMANTIC_CHUNKS_RELATIVE_DIR) + "/" if is_r2(config["destination"]) else None


def ensure_destination_available(config, destination_subject, overwrite, r2_client=None):
    destination = config["destination"]
    if is_local(destination):
        output_dir, legacy_dir = destination_subject / SEMANTIC_CHUNKS_RELATIVE_DIR, destination_subject / LEGACY_SEMANTIC_CHUNKS_RELATIVE_DIR
        existing = [path for path in (output_dir, legacy_dir) if path.exists()]
        if existing and not overwrite:
            if legacy_dir.exists():
                raise SystemExit(f"Legacy combined semantic chunk/vector output exists and is unsupported: {legacy_dir}. Re-run with --overwrite to generate v2 semantic chunks.")
            raise SystemExit(f"Semantic chunk output already exists. Re-run with --overwrite to replace: {output_dir}")
        removed = []
        if overwrite:
            for path in (output_dir, legacy_dir):
                if path.is_dir():
                    shutil.rmtree(path)
                    removed.append(str(path))
                elif path.exists():
                    path.unlink()
                    removed.append(str(path))
        output_dir.mkdir(parents=True, exist_ok=True)
        return {"backend": "local", "status": "replaced_for_overwrite" if removed else "passed", "path": str(output_dir), "legacy_path": str(legacy_dir), "existed_before_run": bool(existing), "removed_for_overwrite": bool(removed), "removed_paths": removed}
    client = r2_client or R2StorageClient.from_env()
    v2_prefix, legacy_prefix = destination_output_prefix(config), legacy_output_prefix(config)
    exists_v2, exists_legacy = client.prefix_has_objects(destination["bucket"], v2_prefix), client.prefix_has_objects(destination["bucket"], legacy_prefix)
    if (exists_v2 or exists_legacy) and not overwrite:
        prefixes = [prefix for prefix, exists in ((v2_prefix, exists_v2), (legacy_prefix, exists_legacy)) if exists]
        label = "legacy combined semantic chunk/vector output" if exists_legacy else "semantic chunk output"
        raise SystemExit(r2_existing_artifacts_error("generate-chunks", destination["bucket"], prefixes, label))
    deleted = []
    if overwrite:
        deleted.extend(client.delete_prefix(destination["bucket"], v2_prefix))
        deleted.extend(client.delete_prefix(destination["bucket"], legacy_prefix))
    return {"backend": "r2", "status": "deleted_for_overwrite" if deleted else "passed", "bucket": destination["bucket"], "prefix": v2_prefix, "legacy_prefix": legacy_prefix, "deleted_keys": deleted, "existed_before_run": exists_v2 or exists_legacy, "removed_for_overwrite": bool(deleted)}


def chunking_metadata(semantic_config: SemanticChunkConfig):
    metadata = {
        "provider": semantic_config.provider, "model": semantic_config.model_name, "model_revision": semantic_config.model_revision,
        "strategy_version": semantic_config.strategy_version, "threshold_percentile": semantic_config.threshold_percentile,
        "min_chars": semantic_config.min_chars, "window_size": semantic_config.window_size, "batch_size": semantic_config.batch_size,
        "normalize_contextual_vectors": semantic_config.normalize_contextual_vectors, "device": semantic_config.device,
    }
    canonical = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return metadata | {"chunking_config_key": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def candidate_manifest_binding(job):
    manifest = job["candidate_manifest"]
    return {"reference": manifest["reference"], "sha256": manifest["sha256"]}


def chunk_payload(chunk):
    return {
        "chunk_index": chunk.index, "text": chunk.text, "sentence_count": chunk.sentence_count,
        "character_count": chunk.char_count, "estimated_token_count": chunk.estimated_token_count,
        "sentence_range": {"start": chunk.start_sentence, "end": chunk.end_sentence},
        "character_span": {"start": chunk.start_char, "end": chunk.end_char, "index_unit": "python-codepoint", "semantics": "zero-based-end-exclusive"},
        "chunk_text_sha256": chunk.chunk_text_sha256,
    }


def chunk_artifact_payload(config, job, source, document, semantic_config, chunk_filename):
    metadata = source["metadata"]
    return {
        "schema_version": SEMANTIC_CHUNKS_ARTIFACT_SCHEMA_VERSION,
        "document": {"category_code": config["naming"]["category_code"], "subject_code": config["naming"]["subject_code"], "title_slug": config["naming"]["title_slug"], "chapter_number": source["chapter_number"], "version": metadata["document"]["version"], "language": config["naming"]["language"]},
        "files": {"chunk_filename": chunk_filename, "source_text_filename": source["text_path"].name, "source_metadata_filename": source["metadata_path"].name},
        "source_references": {
            "candidate_manifest": candidate_manifest_binding(job),
            "content_identity": {key: metadata["content_identity"][key] for key in ("content_key", "normalized_content_sha256", "identity_contract_version")},
            "chapter_text_artifact": metadata["storage"]["artifacts"]["text"], "chapter_metadata_artifact": metadata["storage"]["artifacts"]["metadata"], "source_text_checksum": metadata["integrity"]["artifacts"]["text"],
        },
        "chunking": chunking_metadata(semantic_config) | {"breakpoint_threshold": document.breakpoint_threshold},
        "token_counting": document.to_dict()["token_counting"], "chunks": [chunk_payload(chunk) for chunk in document.chunks],
        "diagnostics": {"source_coverage": {"source_text_whitespace_insensitive_sha256": document.source_text_sha256, "concatenated_chunks_whitespace_insensitive_sha256": document.concatenated_chunks_sha256, "coverage_validated": True, "index_unit": document.index_unit, "span_semantics": document.span_semantics}, "warnings": []},
    }


def chapter_summary(config, source, document, chunk_filename, artifact_sha256):
    metadata = source["metadata"]
    return {
        "chapter_number": source["chapter_number"], "status": "succeeded", "source_text_filename": source["text_path"].name,
        "source_metadata_filename": source["metadata_path"].name, "chunk_filename": chunk_filename,
        "source_text_artifact": metadata["storage"]["artifacts"]["text"], "source_metadata_artifact": metadata["storage"]["artifacts"]["metadata"],
        "chunk_artifact": destination_artifact_reference(config, SEMANTIC_CHUNKS_RELATIVE_DIR / chunk_filename),
        "chunk_artifact_sha256": artifact_sha256, "source_text_checksum": metadata["integrity"]["artifacts"]["text"],
        "content_key": metadata["content_identity"]["content_key"], "normalized_content_sha256": metadata["content_identity"]["normalized_content_sha256"],
        "chunk_count": document.chunk_count, "estimated_token_count": document.estimated_token_count,
        "breakpoint_threshold": document.breakpoint_threshold, "error": None,
    }


def write_chunk_artifacts(config, job, semantic_config, segmenter, progress=print):
    chapters = job["candidate_sources"]
    result = {
        "source_chapter_count": len(job["candidate_manifest"]["chapters"]), "processed_chapter_count": 0,
        "skipped_chapter_count": len(job["candidate_manifest"]["chapters"]) - len(chapters), "failed_chapter_count": 0,
        "chunk_artifacts_written": 0, "chunk_manifest_written": False, "total_chunk_count": 0,
        "total_estimated_token_count": 0, "chapters": [], "audit_report_references": None,
    }
    for position, source in enumerate(chapters, 1):
        prefix = f"[{position}/{len(chapters)}] {source['text_path'].name}:"
        progress(f"{prefix} reading source text")
        text = source["text_path"].read_text(encoding="utf-8")
        progress(f"{prefix} segmenting {len(text)} characters")
        document = segmenter.segment(text, source_name=source["text_path"].name)
        progress(f"{prefix} validating chunks")
        validate_document_for_source(text, document)
        filename = chapter_chunks_output_filename(config, int(source["chapter_number"]))
        path = job["paths"]["semantic_chunks"] / filename
        path.write_text(json.dumps(chunk_artifact_payload(config, job, source, document, semantic_config, filename), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        artifact_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        result["processed_chapter_count"] += 1
        result["chunk_artifacts_written"] += 1
        result["total_chunk_count"] += document.chunk_count
        result["total_estimated_token_count"] += document.estimated_token_count
        result["chapters"].append(chapter_summary(config, source, document, filename, artifact_sha256))
        progress(f"{prefix} wrote {document.chunk_count} chunk(s)")
    return result


def destination_output_location(config, job):
    destination = config["destination"]
    if is_r2(destination):
        prefix = job["destination_output_prefix"]
        return {"backend": "r2", "bucket": destination["bucket"], "prefix": prefix, "url": optional_url(destination.get("url_base"), prefix.rstrip("/"))}
    return {"backend": "local", "path": str(job["paths"]["semantic_chunks"]), "url": None}


def audit_report_references(config, paths):
    return {"json": destination_artifact_reference(config, CHUNKS_REPORT_DIR / paths["json"].name), "markdown": destination_artifact_reference(config, CHUNKS_REPORT_DIR / paths["markdown"].name)}


def write_chunk_manifest(path, config, job, semantic_config, result):
    payload = {
        "schema_version": SEMANTIC_CHUNKS_MANIFEST_SCHEMA_VERSION,
        "run": {"pipeline": config["pipeline"], "source_backend": config["source"].get("backend", "local"), "destination_backend": config["destination"].get("backend", "local"), "output_directory": destination_output_location(config, job)},
        "document": {"category_code": config["naming"]["category_code"], "subject_code": config["naming"]["subject_code"], "title_slug": config["naming"]["title_slug"], "language": config["naming"]["language"], "version": f"v{config['naming']['version']}.{config['naming']['subversion']}"},
        "source_candidate_manifest": candidate_manifest_binding(job), "chunking": chunking_metadata(semantic_config),
        "counts": {"total_chapter_count": result["source_chapter_count"], "processed_chapter_count": result["processed_chapter_count"], "skipped_chapter_count": result["skipped_chapter_count"], "failed_chapter_count": result["failed_chapter_count"], "total_chunk_count": result["total_chunk_count"], "total_estimated_token_count": result["total_estimated_token_count"]},
        "chapters": result["chapters"], "audit_reports": result["audit_report_references"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["chunk_manifest_written"] = True


def publish_generate_chunks_r2(config, job, overwrite, r2_client=None, before_upload=None):
    destination, client = config["destination"], r2_client or R2StorageClient.from_env()
    subject_dir = job["paths"]["destination_subject"]
    uploads = []
    for root in (subject_dir / SEMANTIC_CHUNKS_RELATIVE_DIR, subject_dir / "run_reports" / "generate-chunks"):
        for path in sorted(root.rglob("*")):
            if path.is_file():
                uploads.append((path, subject_artifact_object_key(destination, path.relative_to(subject_dir))))
    chunks = sorted([item for item in uploads if item[0].name.endswith(".chunks.json")], key=lambda item: item[0].name)
    manifest = [item for item in uploads if item[0].name == "semantic_chunks_manifest.json"]
    reports = [item for item in uploads if item[0].parent.name == "generate-chunks"]
    groups = [("chunks", chunks), ("manifest", manifest), ("reports", reports)]
    uploads = [item for _, items in groups for item in items]
    existing = [key for _, key in uploads if client.exists(destination["bucket"], key)]
    if existing and not overwrite:
        raise SystemExit(r2_existing_artifacts_error("generate-chunks", destination["bucket"], existing[:10], "generate-chunks target objects"))
    if before_upload:
        before_upload(uploads)
    print(f"Publishing {len(uploads)} semantic chunk artifact(s) to:")
    print(f"  r2://{destination['bucket']}/{destination['prefix']}/{destination['subject_dir']}/")
    nonempty = [(kind, items) for kind, items in groups if items]
    for group_index, (kind, items) in enumerate(nonempty, start=1):
        if kind == "chunks":
            print(f"[{group_index}/{len(nonempty)}] semantic chunk artifacts: {len(items)} chapters")
            for chapter_index, (path, key) in enumerate(items, start=1):
                upload_r2_file(client, destination, path, key)
                print(f"  [{chapter_index:02d}/{len(items):02d}] {path.stem.removesuffix('.chunks')}")
        else:
            for path, key in items:
                upload_r2_file(client, destination, path, key)
            label = "semantic chunk manifest: semantic_chunks_manifest.json" if kind == "manifest" else f"generate-chunks audit: {', '.join(path.name for path, _ in items)}"
            print(f"[{group_index}/{len(nonempty)}] {label}")
    print(f"Published {len(uploads)} semantic chunk artifact(s) successfully.")
    return uploads


def cleanup_job(job):
    for key in ("source_temp_dir", "destination_temp_dir"):
        if job.get(key):
            job[key].cleanup()
