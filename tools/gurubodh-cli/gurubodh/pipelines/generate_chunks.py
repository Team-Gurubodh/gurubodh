import json
import shutil
import tempfile
from pathlib import Path

from gurubodh.content_identity import validate_content_identity
from gurubodh.constants import (
    ENTRY_POINT_GENERATE_CHUNKS,
    SEMANTIC_CHUNKS_MANIFEST_SCHEMA_VERSION,
    SEMANTIC_CHUNKS_ARTIFACT_SCHEMA_VERSION,
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
    subject_artifact_object_key,
    subject_artifact_prefix,
    upload_r2_file,
)


TEXT_AND_METADATA_RELATIVE_DIR = Path("chapters") / "text_and_metadata"
SEMANTIC_CHUNKS_RELATIVE_DIR = Path("chapters") / SEMANTIC_CHUNKS_OUTPUT_DIR


def run_generate_chunks_job(
    context,
    config,
    entry_point=ENTRY_POINT_GENERATE_CHUNKS,
    overwrite=False,
    config_path=None,
    segmenter: ParagraphSegmenter | None = None,
    r2_client=None,
    progress=print,
):
    semantic_config = config["_semantic_chunk_config"]
    client = r2_client if (is_r2(config["source"]) or is_r2(config["destination"])) else None
    if client is None and (is_r2(config["source"]) or is_r2(config["destination"])):
        client = R2StorageClient.from_env()

    job = prepare_generate_chunks_job(config, overwrite, r2_client=client, progress=progress)
    try:
        validate_selected_content_identities(config, job["paths"]["source_text_and_metadata"])
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
    source_subject, source_temp_dir = materialize_source_subject(config, r2_client=r2_client, progress=progress)
    destination_subject, destination_temp_dir = destination_subject_dir(config)
    destination_preflight = ensure_destination_available(config, destination_subject, overwrite, r2_client=r2_client)
    paths = {
        "source_subject": source_subject,
        "source_text_and_metadata": source_subject / TEXT_AND_METADATA_RELATIVE_DIR,
        "destination_subject": destination_subject,
        "semantic_chunks": destination_subject / SEMANTIC_CHUNKS_RELATIVE_DIR,
        "chunk_manifest": destination_subject / SEMANTIC_CHUNKS_RELATIVE_DIR / "semantic_chunks_manifest.json",
    }
    paths["semantic_chunks"].mkdir(parents=True, exist_ok=True)
    return {
        "paths": paths,
        "source_temp_dir": source_temp_dir,
        "destination_temp_dir": destination_temp_dir,
        "destination_preflight": destination_preflight,
        "destination_output_prefix": destination_output_prefix(config),
    }


def materialize_source_subject(config, r2_client=None, progress=print):
    source = config["source"]
    if is_local(source):
        subject_dir = Path(source["root_dir"]).expanduser() / source["subject_dir"]
        if not subject_dir.is_dir():
            raise SystemExit(f"Configured source subject directory does not exist: {subject_dir}")
        text_dir = subject_dir / TEXT_AND_METADATA_RELATIVE_DIR
        if not text_dir.is_dir():
            raise SystemExit(f"Prepared chapter text directory does not exist: {text_dir}")
        return subject_dir, None

    temp_dir = tempfile.TemporaryDirectory(prefix="gurubodh-generate-chunks-source-")
    subject_dir = Path(temp_dir.name) / source["subject_dir"]
    prefix = subject_artifact_object_key(source, TEXT_AND_METADATA_RELATIVE_DIR) + "/"
    client = r2_client or R2StorageClient.from_env()
    progress(f"listing R2 prepared chapter artifacts r2://{source['bucket']}/{prefix}")
    keys = [key for key in client.list_keys(source["bucket"], prefix) if key.endswith((".txt", ".json"))]
    if not keys:
        raise SystemExit(f"No prepared chapter text artifacts found at r2://{source['bucket']}/{prefix}")
    subject_prefix = subject_artifact_prefix(source)
    for key in keys:
        relative_path = Path(key.removeprefix(subject_prefix))
        target = subject_dir / relative_path
        progress(f"downloading r2://{source['bucket']}/{key}")
        client.download_file(source["bucket"], key, target)
    return subject_dir, temp_dir


def destination_subject_dir(config):
    destination = config["destination"]
    if is_local(destination):
        return Path(destination["root_dir"]).expanduser() / destination["subject_dir"], None
    temp_dir = tempfile.TemporaryDirectory(prefix="gurubodh-generate-chunks-output-")
    return Path(temp_dir.name) / destination["subject_dir"], temp_dir


def destination_output_prefix(config):
    destination = config["destination"]
    if is_r2(destination):
        return subject_artifact_object_key(destination, SEMANTIC_CHUNKS_RELATIVE_DIR) + "/"
    return None


def ensure_destination_available(config, destination_subject, overwrite, r2_client=None):
    destination = config["destination"]
    if is_local(destination):
        output_dir = destination_subject / SEMANTIC_CHUNKS_RELATIVE_DIR
        existed = output_dir.exists()
        removed = False
        if output_dir.exists() and any(output_dir.iterdir()):
            if not overwrite:
                raise SystemExit(f"Semantic chunk output already exists. Re-run with --overwrite to replace: {output_dir}")
            shutil.rmtree(output_dir)
            removed = True
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "backend": "local",
            "status": "passed",
            "path": str(output_dir),
            "existed_before_run": existed,
            "removed_for_overwrite": removed,
        }

    client = r2_client or R2StorageClient.from_env()
    prefix = destination_output_prefix(config)
    if overwrite:
        deleted = client.delete_prefix(destination["bucket"], prefix)
        return {
            "backend": "r2",
            "status": "deleted_for_overwrite",
            "bucket": destination["bucket"],
            "prefix": prefix,
            "deleted_keys": deleted,
            "existed_before_run": bool(deleted),
            "removed_for_overwrite": bool(deleted),
        }
    if client.prefix_has_objects(destination["bucket"], prefix):
        raise SystemExit(
            "R2 semantic chunk output prefix already contains objects. Re-run with --overwrite to replace:\n"
            f"r2://{destination['bucket']}/{prefix}"
        )
    return {
        "backend": "r2",
        "status": "passed",
        "bucket": destination["bucket"],
        "prefix": prefix,
        "deleted_keys": [],
        "existed_before_run": False,
        "removed_for_overwrite": False,
    }


def discover_chapter_sources(config, text_and_metadata_dir):
    text_files = sorted(text_and_metadata_dir.glob("*.txt"))
    if not text_files:
        raise SystemExit(f"No prepared chapter .txt files found in {text_and_metadata_dir}")
    chapter_filter = set(config.get("chapters") or [])
    chapters = []
    for text_path in text_files:
        metadata_path = text_path.with_suffix(".json")
        if not metadata_path.is_file():
            raise SystemExit(f"Prepared chapter metadata is missing for {text_path.name}: {metadata_path}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        chapter_number = metadata["document"]["chapter_number"]
        if chapter_filter and chapter_number not in chapter_filter:
            continue
        chapters.append(
            {
                "chapter_number": chapter_number,
                "text_path": text_path,
                "metadata_path": metadata_path,
                "metadata": metadata,
            }
        )
    if chapter_filter:
        found = {chapter["chapter_number"] for chapter in chapters}
        missing = sorted(chapter_filter - found)
        if missing:
            raise SystemExit(f"Requested chapter metadata not found: {', '.join(missing)}")
    return text_files, chapters


def validate_selected_content_identities(config, text_and_metadata_dir):
    """Fail before model initialization when prepared provenance is unavailable."""
    _, chapters = discover_chapter_sources(config, text_and_metadata_dir)
    for chapter in chapters:
        metadata = chapter["metadata"]
        try:
            validate_content_identity(
                metadata.get("content_identity"),
                metadata["document"]["category_code"],
                metadata["document"]["subject_code"],
                metadata["document"]["language"],
                chapter["text_path"].read_text(encoding="utf-8"),
            )
        except (KeyError, ValueError) as exc:
            raise SystemExit(
                f"Prepared chapter {chapter['metadata_path']} has missing or invalid content_identity. "
                "Regenerate the prepared subject with `gurubodh prep-subject --overwrite` before running generate-chunks. "
                f"Details: {exc}"
            ) from exc


def write_chunk_artifacts(config, job, semantic_config, segmenter, progress=print):
    all_text_files, chapters = discover_chapter_sources(config, job["paths"]["source_text_and_metadata"])
    result = {
        "source_chapter_count": len(all_text_files),
        "processed_chapter_count": 0,
        "skipped_chapter_count": len(all_text_files) - len(chapters),
        "failed_chapter_count": 0,
        "chunk_artifacts_written": 0,
        "chunk_manifest_written": False,
        "total_chunk_count": 0,
        "total_estimated_embedding_token_count": 0,
        "chapters": [],
        "audit_report_references": None,
    }
    total = len(chapters)
    for position, source in enumerate(chapters, 1):
        chapter_number = int(source["chapter_number"])
        text_path = source["text_path"]
        prefix = f"[{position}/{total}] {text_path.name}:"
        progress(f"{prefix} reading source text")
        source_text = text_path.read_text(encoding="utf-8")
        progress(f"{prefix} segmenting {len(source_text)} characters")
        document = segmenter.segment(source_text, source_name=text_path.name)
        progress(f"{prefix} validating chunks and embeddings")
        validate_document_for_source(source_text, document)
        validate_embeddings(document, semantic_config)
        chunk_filename = chapter_chunks_output_filename(config, chapter_number)
        chunk_path = job["paths"]["semantic_chunks"] / chunk_filename
        payload = chunk_artifact_payload(config, source, document, semantic_config, chunk_filename)
        chunk_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["processed_chapter_count"] += 1
        result["chunk_artifacts_written"] += 1
        result["total_chunk_count"] += document.chunk_count
        result["total_estimated_embedding_token_count"] += document.estimated_embedding_token_count
        result["chapters"].append(chapter_summary(config, source, document, chunk_filename))
        progress(f"{prefix} wrote {document.chunk_count} chunk(s)")
    return result


def validate_embeddings(document, semantic_config: SemanticChunkConfig):
    for chunk in document.chunks:
        if chunk.dense_embedding is None:
            raise ValueError(f"{document.source_name}: chunk {chunk.index} is missing a dense embedding")
        if len(chunk.dense_embedding) != semantic_config.embedding_dimension:
            raise ValueError(
                f"{document.source_name}: chunk {chunk.index} embedding dimension "
                f"{len(chunk.dense_embedding)} does not match {semantic_config.embedding_dimension}"
            )


def chunk_artifact_payload(config, source, document, semantic_config, chunk_filename):
    metadata = source["metadata"]
    return {
        "schema_version": SEMANTIC_CHUNKS_ARTIFACT_SCHEMA_VERSION,
        "document": {
            "category_code": config["naming"]["category_code"],
            "subject_code": config["naming"]["subject_code"],
            "title_slug": config["naming"]["title_slug"],
            "chapter_number": source["chapter_number"],
            "version": metadata["document"]["version"],
        },
        "files": {
            "chunk_filename": chunk_filename,
            "source_text_filename": source["text_path"].name,
            "source_metadata_filename": source["metadata_path"].name,
        },
        "source_references": {
            "content_identity": {
                "content_key": metadata["content_identity"]["content_key"],
                "normalized_content_sha256": metadata["content_identity"]["normalized_content_sha256"],
                "identity_contract_version": metadata["content_identity"]["identity_contract_version"],
            },
            "chapter_text_artifact": metadata["storage"]["artifacts"]["text"],
            "chapter_metadata_artifact": metadata["storage"]["artifacts"]["metadata"],
            "source_text_checksum": metadata["integrity"]["artifacts"]["text"],
            "source_text_whitespace_insensitive_sha256": document.source_text_sha256,
            "concatenated_chunks_whitespace_insensitive_sha256": document.concatenated_chunks_sha256,
        },
        "chunking": {
            "provider": document.provider,
            "model": document.model_name,
            "model_revision": semantic_config.model_revision,
            "strategy_version": document.strategy_version,
            "threshold_percentile": document.threshold_percentile,
            "min_chars": document.min_chars,
            "window_size": document.window_size,
            "batch_size": document.batch_size,
            "normalize_embeddings": document.normalize_embeddings,
            "device": document.device,
            "breakpoint_threshold": document.breakpoint_threshold,
        },
        "embedding": embedding_metadata(semantic_config),
        "token_counting": document.to_dict()["token_counting"],
        "chunks": [chunk_payload(chunk) for chunk in document.chunks],
        "diagnostics": {
            "warnings": [],
        },
    }


def embedding_metadata(semantic_config):
    return {
        "provider": semantic_config.provider,
        "model": semantic_config.model_name,
        "model_revision": semantic_config.model_revision,
        "embedding_mode": semantic_config.embedding_mode,
        "embedding_dimension": semantic_config.embedding_dimension,
        "normalize_embeddings": semantic_config.normalize_embeddings,
        "vector_data_type": "float",
        "vector_precision": "float32-or-model-default",
    }


def chunk_payload(chunk):
    return {
        "chunk_index": chunk.index,
        "text": chunk.text,
        "sentence_count": chunk.sentence_count,
        "character_count": chunk.char_count,
        "estimated_embedding_token_count": chunk.estimated_embedding_token_count,
        "sentence_range": {
            "start": chunk.start_sentence,
            "end": chunk.end_sentence,
        },
        "character_span": {
            "start": chunk.start_char,
            "end": chunk.end_char,
            "index_unit": "python-codepoint",
            "semantics": "zero-based-end-exclusive",
        },
        "chunk_text_sha256": chunk.chunk_text_sha256,
        "dense_embedding": chunk.dense_embedding,
    }


def chapter_summary(config, source, document, chunk_filename):
    relative_chunk_path = SEMANTIC_CHUNKS_RELATIVE_DIR / chunk_filename
    metadata = source["metadata"]
    return {
        "chapter_number": source["chapter_number"],
        "status": "succeeded",
        "source_text_filename": source["text_path"].name,
        "source_metadata_filename": source["metadata_path"].name,
        "chunk_filename": chunk_filename,
        "source_text_artifact": metadata["storage"]["artifacts"]["text"],
        "source_metadata_artifact": metadata["storage"]["artifacts"]["metadata"],
        "chunk_artifact": destination_artifact_reference(config, relative_chunk_path),
        "source_text_checksum": metadata["integrity"]["artifacts"]["text"],
        "content_key": metadata["content_identity"]["content_key"],
        "chunk_count": document.chunk_count,
        "estimated_embedding_token_count": document.estimated_embedding_token_count,
        "breakpoint_threshold": document.breakpoint_threshold,
        "error": None,
    }


def write_chunk_manifest(path, config, job, semantic_config, result):
    payload = {
        "schema_version": SEMANTIC_CHUNKS_MANIFEST_SCHEMA_VERSION,
        "run": {
            "pipeline": config["pipeline"],
            "source_backend": config["source"].get("backend", "local"),
            "destination_backend": config["destination"].get("backend", "local"),
            "output_directory": destination_output_location(config, job),
        },
        "document": {
            "category_code": config["naming"]["category_code"],
            "subject_code": config["naming"]["subject_code"],
            "title_slug": config["naming"]["title_slug"],
            "version": f"v{config['naming']['version']}.{config['naming']['subversion']}",
        },
        "provider": semantic_config.provider_metadata(),
        "embedding": embedding_metadata(semantic_config),
        "counts": {
            "total_chapter_count": result["source_chapter_count"],
            "processed_chapter_count": result["processed_chapter_count"],
            "skipped_chapter_count": result["skipped_chapter_count"],
            "failed_chapter_count": result["failed_chapter_count"],
            "total_chunk_count": result["total_chunk_count"],
            "total_estimated_embedding_token_count": result["total_estimated_embedding_token_count"],
        },
        "chapters": result["chapters"],
        "audit_reports": result["audit_report_references"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["chunk_manifest_written"] = True


def destination_output_location(config, job):
    destination = config["destination"]
    if is_r2(destination):
        prefix = job["destination_output_prefix"]
        return {
            "backend": "r2",
            "bucket": destination["bucket"],
            "prefix": prefix,
            "url": optional_url(destination.get("url_base"), prefix.rstrip("/")),
        }
    return {
        "backend": "local",
        "path": str(job["paths"]["semantic_chunks"]),
        "url": None,
    }


def audit_report_references(config, paths):
    return {
        "json": destination_artifact_reference(config, CHUNKS_REPORT_DIR / paths["json"].name),
        "markdown": destination_artifact_reference(config, CHUNKS_REPORT_DIR / paths["markdown"].name),
    }


def publish_generate_chunks_r2(config, job, overwrite, r2_client=None, before_upload=None):
    destination = config["destination"]
    client = r2_client or R2StorageClient.from_env()
    subject_dir = job["paths"]["destination_subject"]
    upload_roots = [
        subject_dir / SEMANTIC_CHUNKS_RELATIVE_DIR,
        subject_dir / "run_reports" / "generate-chunks",
    ]
    uploads = []
    for root in upload_roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative_path = path.relative_to(subject_dir)
            key = subject_artifact_object_key(destination, relative_path)
            uploads.append((path, key))

    chunk_uploads = sorted(
        [item for item in uploads if item[0].name.endswith(".chunks.json")], key=lambda item: item[0].name
    )
    manifest_uploads = [item for item in uploads if item[0].name == "semantic_chunks_manifest.json"]
    report_uploads = [item for item in uploads if item[0].parent.name == "generate-chunks"]
    grouped_uploads = [
        ("chunks", chunk_uploads),
        ("manifest", manifest_uploads),
        ("reports", report_uploads),
    ]
    uploads = [item for _, items in grouped_uploads for item in items]

    existing = []
    for _, key in uploads:
        if client.exists(destination["bucket"], key):
            existing.append(key)
    if existing and not overwrite:
        sample = "\n".join(f"- {key}" for key in existing[:10])
        raise SystemExit(f"R2 destination object(s) already exist:\n{sample}")
    if before_upload:
        before_upload(uploads)
    print(f"Publishing {len(uploads)} chunk artifact(s) to:")
    print(f"  r2://{destination['bucket']}/{destination['prefix']}/{destination['subject_dir']}/")
    nonempty_groups = [(kind, items) for kind, items in grouped_uploads if items]
    for group_index, (kind, items) in enumerate(nonempty_groups, start=1):
        if kind == "chunks":
            print(f"[{group_index}/{len(nonempty_groups)}] semantic chunk artifacts: {len(items)} chapters")
            for chapter_index, (path, key) in enumerate(items, start=1):
                upload_r2_file(client, destination, path, key)
                print(f"  [{chapter_index:02d}/{len(items):02d}] {path.stem.removesuffix('.chunks')}")
        else:
            for path, key in items:
                upload_r2_file(client, destination, path, key)
            if kind == "manifest":
                print(f"[{group_index}/{len(nonempty_groups)}] semantic chunk manifest: semantic_chunks_manifest.json")
            else:
                print(f"[{group_index}/{len(nonempty_groups)}] generate-chunks audit: {', '.join(path.name for path, _ in items)}")
    print(f"Published {len(uploads)} chunk artifact(s) successfully.")
    return uploads


def cleanup_job(job):
    for key in ("source_temp_dir", "destination_temp_dir"):
        temp_dir = job.get(key)
        if temp_dir:
            temp_dir.cleanup()
