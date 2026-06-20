import shutil
from pathlib import Path

from gurubodh_utils.time_utils import timestamp_for_filename


def source_path_for_job(config):
    root_dir = Path(config["source"]["root_dir"]).expanduser()
    relative_path = Path(config["source"]["relative_path"])
    if relative_path.is_absolute():
        raise SystemExit("Config error: source.relative_path must be relative to source.root_dir")
    return root_dir / relative_path


def destination_paths_for_job(config):
    subject_dir = Path(config["destination"]["root_dir"]).expanduser() / config["destination"]["subject_dir"]
    return {
        "subject": subject_dir,
        "full_subject": subject_dir / "full_subject",
        "chapter_msword": subject_dir / "chapters" / "msword",
        "text_and_metadata": subject_dir / "chapters" / "text_and_metadata",
    }


def ensure_job_dirs(paths):
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)


def archive_existing_subject_output(paths):
    subject_dir = paths["subject"]
    if not subject_dir.exists():
        return None
    if not subject_dir.is_dir():
        raise SystemExit(f"Destination subject path exists but is not a directory: {subject_dir}")

    archive_dir = subject_dir.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_base = archive_dir / f"{subject_dir.name}_{timestamp_for_filename()}"
    archive_path = Path(shutil.make_archive(str(archive_base), "zip", subject_dir.parent, subject_dir.name))
    shutil.rmtree(subject_dir)
    print(f"archived existing output to {archive_path}")
    print(f"removed existing output directory {subject_dir}")
    return archive_path

