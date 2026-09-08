"""Temporary interpretations of optional fields in historical complete jobs.

Remove these allowances with the #288 comparison/retirement gate. Composed
inputs declare these values explicitly and do not use the omission allowances.
Historical checkpoint reading is a separate contract in prep_checkpoint.py.
"""


def storage_backend(section):
    return section["backend"] if "backend" in section else "local"


def chapter_split_flags(section):
    return section["flags"] if "flags" in section else []


def summary_chapter_markers(section):
    return section["summary_chapter_markers"] if "summary_chapter_markers" in section else []


def storage_url_base(section):
    return section["url_base"] if "url_base" in section else None
