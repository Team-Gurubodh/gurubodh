def destination_paths_for_subject(subject_dir):
    return {
        "subject": subject_dir,
        "text_and_metadata": subject_dir / "chapters" / "text_and_metadata",
        "unmodified_source_text": subject_dir / "chapters" / "unmodified_source_text",
        "proofreading": subject_dir / "chapters" / "proofreading",
    }


def ensure_job_dirs(paths):
    for key, path in paths.items():
        if key == "proofreading":
            continue
        path.mkdir(parents=True, exist_ok=True)
