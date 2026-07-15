from gurubodh_utils.docx.chapter_split import split_docx_into_chapters
from gurubodh_utils.docx.validate import validate_docx
from gurubodh_utils.naming import full_subject_output_filename
from gurubodh_utils.paths import (
    destination_paths_for_job,
    ensure_job_dirs,
)
from gurubodh_utils.progress import DEFAULT_PROGRESS_REPORTER
from gurubodh_utils.run_report import write_run_reports
from gurubodh_utils.storage import ensure_r2_destination_available, is_r2, materialize_source, publish_r2_destination


def prepare_job_output(config, overwrite=False, reporter=DEFAULT_PROGRESS_REPORTER):
    reporter.report("preparing destination")
    ensure_r2_destination_available(config, overwrite, reporter=reporter)

    reporter.report("materializing source")
    source_path, source_temp_dir = materialize_source(config, reporter=reporter)
    if not source_path.exists():
        raise SystemExit(f"Configured source file does not exist: {source_path}")
    if source_path.suffix.lower() != ".docx":
        raise SystemExit(f"Configured source file must be .docx: {source_path}")
    reporter.report(f"materialized source at {source_path}")

    paths, destination_temp_dir = destination_paths_for_job(config, overwrite)
    ensure_job_dirs(paths)
    reporter.report(f"prepared destination at {paths['subject']}")

    return {
        "source_path": source_path,
        "source_temp_dir": source_temp_dir,
        "destination_temp_dir": destination_temp_dir,
        "paths": paths,
        "full_docx": paths["full_subject"] / full_subject_output_filename(config, ".docx"),
        "full_text": paths["full_subject"] / full_subject_output_filename(config, ".txt"),
    }


def validate_and_split(config, result, paths, entry_point, reporter=DEFAULT_PROGRESS_REPORTER):
    reporter.report("validating DOCX")
    validate_docx(result["output_path"])
    reporter.report(f"validated DOCX {result['output_path']}")

    chapter_split = config["chapter_split"]
    if chapter_split.get("enabled"):
        reporter.report("splitting chapters")
        split_docx_into_chapters(
            result["output_path"],
            chapter_split,
            paths["chapter_msword"],
            paths["text_and_metadata"],
            config,
            result["converter_counts"],
            entry_point,
            reporter=reporter,
        )
    else:
        reporter.report("chapter splitting disabled")


def publish_job_output(config, job, overwrite=False, reporter=DEFAULT_PROGRESS_REPORTER):
    if is_r2(config["destination"]):
        reporter.report("publishing artifacts to R2")
        publish_r2_destination(config, job["paths"]["subject"], overwrite, reporter=reporter)
        reporter.report("published artifacts to R2")


def write_job_run_reports(
    config,
    job,
    result,
    entry_point,
    config_path,
    overwrite,
    project_root,
    reporter=DEFAULT_PROGRESS_REPORTER,
):
    reporter.report("writing run audit reports")
    return write_run_reports(
        config,
        job["paths"],
        result,
        entry_point,
        config_path,
        overwrite,
        project_root,
        reporter,
    )
