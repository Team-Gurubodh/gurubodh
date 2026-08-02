from gurubodh.docx.chapter_split import split_docx_into_chapters
from gurubodh.content_manifest import write_chapter_content_manifest
from gurubodh.docx.validate import validate_docx
from gurubodh.naming import full_subject_output_filename
from gurubodh.paths import (
    destination_paths_for_job,
    ensure_job_dirs,
)
import shutil
from pathlib import Path

from gurubodh.storage import (
    CANONICAL_ARTIFACT_DIRS,
    CANONICAL_ARTIFACT_FILES,
    ensure_r2_destination_available,
    invalidate_local_semantic_artifacts,
    invalidate_r2_semantic_artifacts,
    is_local,
    is_r2,
    materialize_source,
    publish_r2_destination,
)


def staging_progress(subject_dir):
    print("Preparing canonical artifacts in staging directory:")
    print(f"  {subject_dir}")
    print("Outputs: full_subject/, chapters/msword/, and chapters/text_and_metadata/")

    def report(stage, *paths):
        relative_paths = [Path(path).relative_to(subject_dir) for path in paths]
        if stage == "validate":
            print(f"[{stage}] wrote {relative_paths[0]}")
            return

        artifact_types = {
            ".docx": "DOCX",
            ".txt": "text",
            ".json": "metadata",
        }
        types = [artifact_types.get(path.suffix, path.suffix.lstrip(".")) for path in relative_paths]
        stem = relative_paths[0].stem
        if stage == "prepare":
            location = relative_paths[0].parent / stem
        else:
            location = Path(stem)
        print(f"[{stage}] {location} ({', '.join(types)})")

    return report


def prepare_job_output(config, overwrite=False):
    r2_preflight = ensure_r2_destination_available(config, overwrite, command="prep-subject")
    source_path, source_temp_dir = materialize_source(config)
    if not source_path.exists():
        raise SystemExit(f"Configured source file does not exist: {source_path}")
    if source_path.suffix.lower() != ".docx":
        raise SystemExit(f"Configured source file must be .docx: {source_path}")

    paths, destination_temp_dir, local_destination = destination_paths_for_job(config, overwrite)
    ensure_job_dirs(paths)
    progress = staging_progress(paths["subject"])

    return {
        "source_path": source_path,
        "source_temp_dir": source_temp_dir,
        "destination_temp_dir": destination_temp_dir,
        "local_destination": local_destination,
        "published_subject": Path(local_destination["path"]) if local_destination else None,
        "r2_preflight": r2_preflight,
        "paths": paths,
        "progress": progress,
        "full_docx": paths["full_subject"] / full_subject_output_filename(config, ".docx"),
        "full_text": paths["full_subject"] / full_subject_output_filename(config, ".txt"),
    }


def validate_and_split(config, result, paths, entry_point, progress=None):
    validate_docx(result["output_path"])

    chapter_split = config["chapter_split"]
    if chapter_split.get("enabled"):
        outputs = split_docx_into_chapters(
            result["output_path"],
            chapter_split,
            paths["chapter_msword"],
            paths["text_and_metadata"],
            config,
            result["converter_counts"],
            entry_point,
            progress=progress,
        )
        if outputs:
            manifest_path = write_chapter_content_manifest(config, paths)
            if progress:
                progress("validate", manifest_path)
            else:
                print(f"wrote {manifest_path}")
        return outputs
    return []


def publish_job_output(config, job, overwrite=False, before_upload=None):
    if is_r2(config["destination"]):
        uploads = publish_r2_destination(config, job["paths"]["subject"], overwrite, before_upload=before_upload, command="prep-subject")
        if overwrite:
            job["semantic_invalidation"] = invalidate_r2_semantic_artifacts(config)
            if job["semantic_invalidation"]["invalidated"]:
                print("Derived semantic chunks were invalidated because canonical content was overwritten. Run gurubodh generate-chunks --config <generate-chunks-job> before relying on RAG/chunk outputs.")
            else:
                print("No derived semantic artifacts existed; no semantic invalidation was necessary.")
        return uploads
    if is_local(config["destination"]) and overwrite:
        _promote_local_canonical_artifacts(job)
        job["semantic_invalidation"] = invalidate_local_semantic_artifacts(job["paths"]["subject"])
        if job["semantic_invalidation"]["invalidated"]:
            print(
                "Derived semantic chunks were invalidated because canonical content was overwritten. "
                "Run gurubodh generate-chunks --config <generate-chunks-job> before relying on RAG/chunk outputs."
            )
        else:
            print("No derived semantic artifacts existed; no semantic invalidation was necessary.")
    if is_local(config["destination"]):
        _promote_local_canonical_artifacts(job)
    return []


def _promote_local_canonical_artifacts(job):
    staging_subject = job["paths"]["subject"]
    published_subject = job["published_subject"]
    if staging_subject == published_subject:
        return
    print(f"Promoting canonical artifacts to: {published_subject}")
    for relative_path in (*CANONICAL_ARTIFACT_DIRS, *CANONICAL_ARTIFACT_FILES):
        source = staging_subject / relative_path
        target = published_subject / relative_path
        if not source.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
    job["paths"] = {
        key: (published_subject / value.relative_to(staging_subject)) if isinstance(value, type(staging_subject)) and value.is_relative_to(staging_subject) else value
        for key, value in job["paths"].items()
    }
