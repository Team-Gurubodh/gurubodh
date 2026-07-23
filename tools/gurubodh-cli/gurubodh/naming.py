def version_label(config):
    naming = config["naming"]
    return f"v{naming['version']}.{naming['subversion']}"


def chapter_output_filename(config, chapter_number, extension):
    naming = config["naming"]
    parts = [
        naming["category_code"],
        naming["subject_code"],
        naming["title_slug"],
        f"{chapter_number:03d}",
        version_label(config),
    ]
    return "_".join(parts) + extension


def chapter_chunks_output_filename(config, chapter_number):
    return chapter_output_filename(config, chapter_number, ".chunks.json")


def full_subject_output_filename(config, extension):
    naming = config["naming"]
    parts = [
        naming["category_code"],
        naming["subject_code"],
        naming["title_slug"],
        "full",
        version_label(config),
    ]
    return "_".join(parts) + extension
