from gurubodh.docx.chapter_split import split_docx_into_chapters
from gurubodh.docx.validate import validate_docx
from gurubodh.naming import full_subject_output_filename
from gurubodh.paths import (
    destination_paths_for_job,
    ensure_job_dirs,
)
from gurubodh.storage import ensure_r2_destination_available, is_r2, materialize_source, publish_r2_destination


def prepare_job_output(config, overwrite=False):
    r2_preflight = ensure_r2_destination_available(config, overwrite)
    source_path, source_temp_dir = materialize_source(config)
    if not source_path.exists():
        raise SystemExit(f"Configured source file does not exist: {source_path}")
    if source_path.suffix.lower() != ".docx":
        raise SystemExit(f"Configured source file must be .docx: {source_path}")

    paths, destination_temp_dir, local_destination = destination_paths_for_job(config, overwrite)
    ensure_job_dirs(paths)

    return {
        "source_path": source_path,
        "source_temp_dir": source_temp_dir,
        "destination_temp_dir": destination_temp_dir,
        "local_destination": local_destination,
        "r2_preflight": r2_preflight,
        "paths": paths,
        "full_docx": paths["full_subject"] / full_subject_output_filename(config, ".docx"),
        "full_text": paths["full_subject"] / full_subject_output_filename(config, ".txt"),
    }


def validate_and_split(config, result, paths, entry_point):
    validate_docx(result["output_path"])

    chapter_split = config["chapter_split"]
    if chapter_split.get("enabled"):
        return split_docx_into_chapters(
            result["output_path"],
            chapter_split,
            paths["chapter_msword"],
            paths["text_and_metadata"],
            config,
            result["converter_counts"],
            entry_point,
        )
    return []


def publish_job_output(config, job, overwrite=False, before_upload=None):
    if is_r2(config["destination"]):
        return publish_r2_destination(config, job["paths"]["subject"], overwrite, before_upload=before_upload)
    return []
