"""Candidate-manifest-bound semantic chunk generation."""

import hashlib
import json
from pathlib import Path

from gurubodh.canonical_source import (
    CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH,
    TEXT_AND_METADATA_RELATIVE_DIR,
    materialize_source_subject,
    revalidate_source_release,
    validate_materialized_release,
)
from gurubodh.constants import (
    ENTRY_POINT_GENERATE_CHUNKS,
    SEMANTIC_CHUNKS_ARTIFACT_SCHEMA_VERSION,
    SEMANTIC_CHUNKS_MANIFEST_SCHEMA_VERSION,
    SEMANTIC_CHUNKS_OUTPUT_DIR,
)
from gurubodh.contracts import (
    ChunkChapterSummary,
    ChunkGenerationJob,
    ChunkGenerationPaths,
    ChunkGenerationSummary,
    GenerateChunksJob,
    GenerationStatus,
    MaterializedChapterSource,
    MaterializedSource,
)
from gurubodh.derived_artifact_lifecycle import (
    DerivedArtifactDefinition,
    destination_subject_dir,
    run_derived_artifact_lifecycle,
)
from gurubodh.errors import ProcessingError
from gurubodh.generate_chunks_audit import GenerateChunksAuditWriter
from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig
from gurubodh.ml.semantic_chunking.file_io import validate_document_for_source
from gurubodh.ml.semantic_chunking.segmenter import ParagraphSegmenter, SemanticChunkingParagraphSegmenter
from gurubodh.naming import chapter_chunks_output_filename
from gurubodh.schema_validation import write_json_artifact
from gurubodh.storage import (
    CHUNKS_REPORT_DIR,
    destination_artifact_reference,
    is_r2,
    optional_url,
    subject_artifact_object_key,
)


SEMANTIC_CHUNKS_RELATIVE_DIR = Path("chapters") / SEMANTIC_CHUNKS_OUTPUT_DIR
LEGACY_SEMANTIC_CHUNKS_RELATIVE_DIR = Path("chapters") / "semantic_chunks_and_embeddings"


def destination_output_prefix(config: GenerateChunksJob) -> str | None:
    return subject_artifact_object_key(config["destination"], SEMANTIC_CHUNKS_RELATIVE_DIR) + "/" if is_r2(config["destination"]) else None


def chunking_metadata(semantic_config: SemanticChunkConfig):
    metadata = {
        "provider": semantic_config.provider, "model": semantic_config.model_name, "model_revision": semantic_config.model_revision,
        "strategy_version": semantic_config.strategy_version, "threshold_percentile": semantic_config.threshold_percentile,
        "min_chars": semantic_config.min_chars, "window_size": semantic_config.window_size, "batch_size": semantic_config.batch_size,
        "normalize_contextual_vectors": semantic_config.normalize_contextual_vectors, "device": semantic_config.device,
    }
    canonical = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return metadata | {"chunking_config_key": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def candidate_manifest_binding(job: ChunkGenerationJob):
    return job.candidate_manifest.serialized_binding()


def chunk_payload(chunk):
    return {
        "chunk_index": chunk.index, "text": chunk.text, "sentence_count": chunk.sentence_count,
        "character_count": chunk.char_count, "estimated_token_count": chunk.estimated_token_count,
        "sentence_range": {"start": chunk.start_sentence, "end": chunk.end_sentence},
        "character_span": {"start": chunk.start_char, "end": chunk.end_char, "index_unit": "python-codepoint", "semantics": "zero-based-end-exclusive"},
        "chunk_text_sha256": chunk.chunk_text_sha256,
    }


def chunk_artifact_payload(
    config: GenerateChunksJob,
    job: ChunkGenerationJob,
    source: MaterializedChapterSource,
    document,
    semantic_config: SemanticChunkConfig,
    chunk_filename: str,
):
    metadata = source.metadata
    return {
        "schema_version": SEMANTIC_CHUNKS_ARTIFACT_SCHEMA_VERSION,
        "document": {"category_code": config["naming"]["category_code"], "subject_code": config["naming"]["subject_code"], "title_slug": config["naming"]["title_slug"], "chapter_number": source.chapter_number, "version": metadata["document"]["version"], "language": config["naming"]["language"]},
        "files": {"chunk_filename": chunk_filename, "source_text_filename": source.text_path.name, "source_metadata_filename": source.metadata_path.name},
        "source_references": {
            "candidate_manifest": candidate_manifest_binding(job),
            "content_identity": {key: metadata["content_identity"][key] for key in ("content_key", "normalized_content_sha256", "identity_contract_version")},
            "chapter_text_artifact": metadata["storage"]["artifacts"]["text"], "chapter_metadata_artifact": metadata["storage"]["artifacts"]["metadata"], "source_text_checksum": metadata["integrity"]["artifacts"]["text"],
        },
        "chunking": chunking_metadata(semantic_config) | {"breakpoint_threshold": document.breakpoint_threshold},
        "token_counting": document.to_dict()["token_counting"], "chunks": [chunk_payload(chunk) for chunk in document.chunks],
        "diagnostics": {"source_coverage": {"source_text_whitespace_insensitive_sha256": document.source_text_sha256, "concatenated_chunks_whitespace_insensitive_sha256": document.concatenated_chunks_sha256, "coverage_validated": True, "index_unit": document.index_unit, "span_semantics": document.span_semantics}, "warnings": []},
    }


def chapter_summary(
    config: GenerateChunksJob,
    source: MaterializedChapterSource,
    document,
    chunk_filename: str,
    artifact_sha256: str,
) -> ChunkChapterSummary:
    metadata = source.metadata
    return ChunkChapterSummary(
        chapter_number=source.chapter_number,
        status=GenerationStatus.SUCCEEDED,
        source_text_filename=source.text_path.name,
        source_metadata_filename=source.metadata_path.name,
        chunk_filename=chunk_filename,
        source_text_artifact=metadata["storage"]["artifacts"]["text"],
        source_metadata_artifact=metadata["storage"]["artifacts"]["metadata"],
        chunk_artifact=destination_artifact_reference(config, SEMANTIC_CHUNKS_RELATIVE_DIR / chunk_filename),
        chunk_artifact_sha256=artifact_sha256,
        source_text_checksum=metadata["integrity"]["artifacts"]["text"],
        content_key=metadata["content_identity"]["content_key"],
        normalized_content_sha256=metadata["content_identity"]["normalized_content_sha256"],
        chunk_count=document.chunk_count,
        estimated_token_count=document.estimated_token_count,
        breakpoint_threshold=document.breakpoint_threshold,
    )


def write_chunk_artifacts(
    config: GenerateChunksJob,
    job: ChunkGenerationJob,
    semantic_config: SemanticChunkConfig,
    segmenter: ParagraphSegmenter,
    progress=print,
    summary: ChunkGenerationSummary | None = None,
) -> ChunkGenerationSummary:
    chapters = job.candidate_sources
    result = summary or ChunkGenerationSummary(source_chapter_count=0)
    result.source_chapter_count = len(job.candidate_manifest.chapters)
    result.skipped_chapter_count = len(job.candidate_manifest.chapters) - len(chapters)
    for position, source in enumerate(chapters, 1):
        prefix = f"[{position}/{len(chapters)}] {source.text_path.name}:"
        filename = chapter_chunks_output_filename(config, int(source.chapter_number))
        metadata = source.metadata
        in_progress = ChunkChapterSummary(
            chapter_number=source.chapter_number,
            status=GenerationStatus.RUNNING,
            source_text_filename=source.text_path.name,
            source_metadata_filename=source.metadata_path.name,
            chunk_filename=filename,
            source_text_artifact=metadata["storage"]["artifacts"]["text"],
            source_metadata_artifact=metadata["storage"]["artifacts"]["metadata"],
            content_key=metadata["content_identity"]["content_key"],
            normalized_content_sha256=metadata["content_identity"]["normalized_content_sha256"],
        )
        result.chapters.append(in_progress)
        try:
            progress(f"{prefix} reading source text")
            text = source.text_path.read_text(encoding="utf-8")
            progress(f"{prefix} segmenting {len(text)} characters")
            document = segmenter.segment(text, source_name=source.text_path.name)
            progress(f"{prefix} validating chunks")
            validate_document_for_source(text, document)
            path = job.paths.semantic_chunks / filename
            write_json_artifact(
                path,
                chunk_artifact_payload(
                    config, job, source, document, semantic_config, filename
                ),
                "semantic chunks",
            )
            artifact_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            completed = chapter_summary(
                config, source, document, filename, artifact_sha256
            )
            result.chapters[-1] = completed
            result.processed_chapter_count += 1
            result.chunk_artifacts_written += 1
            result.total_chunk_count += document.chunk_count
            result.total_estimated_token_count += document.estimated_token_count
            progress(f"{prefix} wrote {document.chunk_count} chunk(s)")
        except BaseException as error:
            in_progress.status = GenerationStatus.FAILED
            in_progress.error = str(error)[:500] or error.__class__.__name__
            result.failed_chapter_count += 1
            raise
    return result


def destination_output_location(
    config: GenerateChunksJob, job: ChunkGenerationJob
):
    destination = config["destination"]
    if is_r2(destination):
        prefix = job.destination_output_prefix
        return {"backend": "r2", "bucket": destination["bucket"], "prefix": prefix, "url": optional_url(destination.get("url_base"), prefix.rstrip("/"))}
    return {
        "backend": "local",
        "path": str(job.paths.final_semantic_chunks),
        "url": None,
    }


def build_chunk_manifest(
    config,
    job: ChunkGenerationJob,
    semantic_config,
    result: ChunkGenerationSummary,
):
    result_payload = result.to_payload()
    return {
        "schema_version": SEMANTIC_CHUNKS_MANIFEST_SCHEMA_VERSION,
        "run": {"pipeline": config["pipeline"], "source_backend": config["source"].get("backend", "local"), "destination_backend": config["destination"].get("backend", "local"), "output_directory": destination_output_location(config, job)},
        "document": {"category_code": config["naming"]["category_code"], "subject_code": config["naming"]["subject_code"], "title_slug": config["naming"]["title_slug"], "language": config["naming"]["language"], "version": f"v{config['naming']['version']}.{config['naming']['subversion']}"},
        "source_candidate_manifest": candidate_manifest_binding(job), "chunking": chunking_metadata(semantic_config),
        "counts": {"total_chapter_count": result.source_chapter_count, "processed_chapter_count": result.processed_chapter_count, "skipped_chapter_count": result.skipped_chapter_count, "failed_chapter_count": result.failed_chapter_count, "total_chunk_count": result.total_chunk_count, "total_estimated_token_count": result.total_estimated_token_count},
        "chapters": result_payload["chapters"], "audit_reports": result.audit_report_references,
    }


def validate_chunk_staged_package(
    config,
    job: ChunkGenerationJob,
    result: ChunkGenerationSummary,
    staged_output,
    readiness_manifest,
):
    manifest = json.loads(Path(readiness_manifest).read_text(encoding="utf-8"))
    chapter_payloads = [chapter.to_payload() for chapter in result.chapters]
    expected_names = {chapter.chunk_filename for chapter in result.chapters}
    actual_names = {path.name for path in Path(staged_output).glob("*.chunks.json")}
    if expected_names != actual_names:
        raise ProcessingError("Staged chunk files do not exactly match generated chapter results.")
    if manifest.get("chapters") != chapter_payloads:
        raise ProcessingError("Semantic chunk readiness manifest chapters do not match staged artifacts.")
    counts = manifest.get("counts", {})
    expected_counts = {
        "total_chapter_count": result.source_chapter_count,
        "processed_chapter_count": result.processed_chapter_count,
        "skipped_chapter_count": result.skipped_chapter_count,
        "failed_chapter_count": result.failed_chapter_count,
        "total_chunk_count": result.total_chunk_count,
        "total_estimated_token_count": result.total_estimated_token_count,
    }
    if counts != expected_counts:
        raise ProcessingError("Semantic chunk readiness manifest counts do not match generation results.")
    for chapter in result.chapters:
        path = Path(staged_output) / chapter.chunk_filename
        if hashlib.sha256(path.read_bytes()).hexdigest() != chapter.chunk_artifact_sha256:
            raise ProcessingError(f"Staged chunk checksum changed for chapter {chapter.chapter_number}.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("source_references", {}).get("candidate_manifest") != candidate_manifest_binding(job):
            raise ProcessingError(f"Staged chunk source binding is invalid for chapter {chapter.chapter_number}.")
    result.chunk_manifest_written = True


class GenerateChunksWorkflow:
    def __init__(
        self,
        context,
        config,
        config_path,
        entry_point,
        overwrite,
        destination_subject,
        segmenter,
    ):
        self.config = config
        self.semantic_config = config.semantic_chunk_config
        self.destination_subject = Path(destination_subject)
        self.segmenter = segmenter
        self.job = None
        self.result = ChunkGenerationSummary(source_chapter_count=0)
        self.audit = GenerateChunksAuditWriter(
            context,
            config_path,
            config,
            entry_point,
            overwrite,
            destination_subject,
        )
        self.result.audit_report_references = self.audit.references

    def materialize_and_validate_source(self, r2_client, progress):
        subject, temporary, manifest = materialize_source_subject(
            self.config, "generate-chunks", r2_client, progress
        )
        try:
            sources = validate_materialized_release(
                self.config,
                subject,
                manifest,
                "generate-chunks",
                r2_client,
            )
        except BaseException:
            if temporary:
                temporary.cleanup()
            raise
        self.result.source_chapter_count = len(manifest.chapters)
        self.result.skipped_chapter_count = len(manifest.chapters) - len(sources)
        return MaterializedSource(subject, manifest, sources, temporary)

    def generate_staged_artifacts(self, source, staged_output, progress):
        self.job = ChunkGenerationJob(
            paths=ChunkGenerationPaths(
                source_subject=source.subject_dir,
                source_text_and_metadata=source.subject_dir / TEXT_AND_METADATA_RELATIVE_DIR,
                candidate_manifest=source.subject_dir / CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH,
                destination_subject=self.destination_subject,
                semantic_chunks=staged_output,
                final_semantic_chunks=self.destination_subject / SEMANTIC_CHUNKS_RELATIVE_DIR,
                chunk_manifest=staged_output / "semantic_chunks_manifest.json",
            ),
            candidate_sources=tuple(source.chapters),
            candidate_manifest=source.candidate_manifest,
            destination_output_prefix=destination_output_prefix(self.config),
        )
        # Every source check completed before the lazy segmenter can load a model.
        segmenter = self.segmenter or SemanticChunkingParagraphSegmenter(
            self.semantic_config, progress=progress
        )
        self.result = write_chunk_artifacts(
            self.config,
            self.job,
            self.semantic_config,
            segmenter,
            progress=progress,
            summary=self.result,
        )
        self.result.audit_report_references = self.audit.references
        return self.result

    def build_readiness_manifest(self, source, generation):
        return build_chunk_manifest(
            self.config, self.job, self.semantic_config, generation
        )

    def validate_staged_package(
        self, source, generation, staged_output, readiness_manifest
    ):
        validate_chunk_staged_package(
            self.config,
            self.job,
            generation,
            staged_output,
            readiness_manifest,
        )

    def write_audit(
        self,
        status,
        lifecycle,
        source,
        generation,
        publication,
        failure,
        announce,
    ):
        report = self.audit.write(
            status=status,
            candidate_manifest=(
                source.candidate_manifest.to_internal_payload() if source else None
            ),
            result=(
                generation.to_payload()
                if generation is not None
                else self.result.to_payload()
            ),
            publication=publication,
            failure=failure,
            lifecycle=lifecycle.as_dict(),
            destination_subject=self.destination_subject,
            announce=announce,
        )
        return report


def run_generate_chunks_job(
    context,
    config: GenerateChunksJob,
    entry_point=ENTRY_POINT_GENERATE_CHUNKS,
    overwrite=False,
    config_path=None,
    segmenter: ParagraphSegmenter | None = None,
    r2_client=None,
    progress=print,
) -> ChunkGenerationSummary:
    definition = DerivedArtifactDefinition(
        command_name="generate-chunks",
        output_relative_dir=SEMANTIC_CHUNKS_RELATIVE_DIR,
        readiness_manifest_filename="semantic_chunks_manifest.json",
        readiness_manifest_artifact_name="semantic chunks manifest",
        report_relative_dir=CHUNKS_REPORT_DIR,
        legacy_output_relative_dirs=(LEGACY_SEMANTIC_CHUNKS_RELATIVE_DIR,),
    )
    destination_subject, destination_temporary = destination_subject_dir(
        config, definition.command_name
    )
    workflow = GenerateChunksWorkflow(
        context,
        config,
        config_path,
        entry_point,
        overwrite,
        destination_subject,
        segmenter,
    )
    lifecycle = run_derived_artifact_lifecycle(
        config,
        definition,
        workflow,
        overwrite=overwrite,
        r2_client=r2_client,
        progress=progress,
        destination_subject=destination_subject,
        destination_temporary=destination_temporary,
        source_revalidator=revalidate_source_release,
    )
    result = lifecycle.generation
    result.publication = lifecycle.publication
    result.audit_report = lifecycle.audit_report
    result.lifecycle = lifecycle.lifecycle
    return result
