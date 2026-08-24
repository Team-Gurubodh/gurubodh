import tempfile
from pathlib import Path

from gurubodh.storage import ensure_local_destination, is_local, subject_output_root


def destination_paths_for_subject(subject_dir):
    return {
        "subject": subject_dir,
        "full_subject": subject_dir / "full_subject",
        "chapter_msword": subject_dir / "chapters" / "msword",
        "text_and_metadata": subject_dir / "chapters" / "text_and_metadata",
        "proofreading": subject_dir / "chapters" / "proofreading",
    }


def ensure_job_dirs(paths):
    for key, path in paths.items():
        if key == "proofreading":
            continue
        path.mkdir(parents=True, exist_ok=True)


def destination_paths_for_job(config, overwrite=False):
    output_root = subject_output_root(config)
    temp_dir = None
    if isinstance(output_root, tuple):
        subject_dir, temp_dir = output_root
    else:
        subject_dir = output_root

    destination_info = None
    if is_local(config["destination"]):
        destination_info = ensure_local_destination(subject_dir, overwrite, command="prep-subject")
        # Build canonical artifacts outside the published tree. Promotion happens
        # only after DOCX validation and chapter splitting have succeeded.
        temp_dir = tempfile.TemporaryDirectory(prefix="gurubodh-prep-subject-output-")
        subject_dir = Path(temp_dir.name) / config["destination"]["subject_dir"]

    paths = destination_paths_for_subject(subject_dir)
    return paths, temp_dir, destination_info
