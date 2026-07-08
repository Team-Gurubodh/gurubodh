from gurubodh_utils.docx.chapter_split import split_docx_into_chapters
from gurubodh_utils.docx.validate import validate_docx
from gurubodh_utils.naming import full_subject_output_filename
from gurubodh_utils.paths import (
    destination_paths_for_job,
    ensure_job_dirs,
)
from gurubodh_utils.storage import ensure_r2_destination_available, is_r2, materialize_source, publish_r2_destination


def prepare_job_output(config, overwrite=False):
    ensure_r2_destination_available(config, overwrite)
    source_path, source_temp_dir = materialize_source(config)
    if not source_path.exists():
        raise SystemExit(f"Configured source file does not exist: {source_path}")
    if source_path.suffix.lower() != ".docx":
        raise SystemExit(f"Configured source file must be .docx: {source_path}")

    paths, destination_temp_dir = destination_paths_for_job(config, overwrite)
    ensure_job_dirs(paths)

    return {
        "source_path": source_path,
        "source_temp_dir": source_temp_dir,
        "destination_temp_dir": destination_temp_dir,
        "paths": paths,
        "full_docx": paths["full_subject"] / full_subject_output_filename(config, ".docx"),
        "full_text": paths["full_subject"] / full_subject_output_filename(config, ".txt"),
    }


def validate_and_split(config, result, paths, entry_point):
    validate_docx(result["output_path"])

    chapter_split = config["chapter_split"]
    if chapter_split.get("enabled"):
        split_docx_into_chapters(
            result["output_path"],
            chapter_split,
            paths["chapter_msword"],
            paths["text_and_metadata"],
            config,
            result["converter_counts"],
            entry_point,
        )


def publish_job_output(config, job, overwrite=False):
    if is_r2(config["destination"]):
        publish_r2_destination(config, job["paths"]["subject"], overwrite)
