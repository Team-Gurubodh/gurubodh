from gurubodh_utils.docx.chapter_split import split_docx_into_chapters
from gurubodh_utils.docx.validate import validate_docx
from gurubodh_utils.naming import full_subject_output_filename
from gurubodh_utils.paths import (
    archive_existing_subject_output,
    destination_paths_for_job,
    ensure_job_dirs,
    source_path_for_job,
)


def prepare_job_output(config):
    source_path = source_path_for_job(config)
    if not source_path.exists():
        raise SystemExit(f"Configured source file does not exist: {source_path}")
    if source_path.suffix.lower() != ".docx":
        raise SystemExit(f"Configured source file must be .docx: {source_path}")

    paths = destination_paths_for_job(config)
    archive_existing_subject_output(paths)
    ensure_job_dirs(paths)

    return {
        "source_path": source_path,
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

