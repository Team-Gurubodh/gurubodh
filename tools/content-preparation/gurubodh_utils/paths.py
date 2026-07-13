from pathlib import Path

from gurubodh_utils.storage import (
    collect_formatted_artifacts,
    ensure_local_destination,
    is_local,
    restore_formatted_artifacts,
    subject_output_root,
)


def destination_paths_for_subject(subject_dir):
    return {
        "subject": subject_dir,
        "full_subject": subject_dir / "full_subject",
        "chapter_msword": subject_dir / "chapters" / "msword",
        "text_and_metadata": subject_dir / "chapters" / "text_and_metadata",
    }


def ensure_job_dirs(paths):
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)


def destination_paths_for_job(config, overwrite=False):
    output_root = subject_output_root(config)
    temp_dir = None
    if isinstance(output_root, tuple):
        subject_dir, temp_dir = output_root
    else:
        subject_dir = output_root

    if is_local(config["destination"]):
        preserved_formatted_artifacts = {}
        formatting_config = config.get("formatting", {})
        if (
            overwrite
            and formatting_config.get("enabled")
            and formatting_config.get("regenerate") == "when-source-checksum-changes"
        ):
            preserved_formatted_artifacts = collect_formatted_artifacts(subject_dir)
        ensure_local_destination(subject_dir, overwrite)
        restore_formatted_artifacts(subject_dir, preserved_formatted_artifacts)

    paths = destination_paths_for_subject(subject_dir)
    return paths, temp_dir
