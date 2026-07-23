from gurubodh.config import load_prep_subject_job
from gurubodh.constants import (
    ENTRY_POINT_LEGACY_DOCX_TO_UNICODE,
    ENTRY_POINT_PREP_SUBJECT,
    ENTRY_POINT_UNICODE_DOCX_INGEST,
    PIPELINE_LEGACY_DOCX_TO_UNICODE,
    PIPELINE_UNICODE_DOCX_INGEST,
)
from gurubodh.pipelines.legacy_docx_to_unicode import run_legacy_docx_to_unicode
from gurubodh.pipelines.unicode_docx_ingest import run_unicode_docx_ingest


def run_configured_job(context, config_path, entry_point=ENTRY_POINT_PREP_SUBJECT, overwrite=False):
    config = load_prep_subject_job(config_path)
    pipeline = config["pipeline"]
    if pipeline == PIPELINE_UNICODE_DOCX_INGEST:
        return run_unicode_docx_ingest(context, config, entry_point, overwrite, config_path)
    if pipeline == PIPELINE_LEGACY_DOCX_TO_UNICODE:
        return run_legacy_docx_to_unicode(context, config, entry_point, overwrite, config_path)
    raise SystemExit(f"Config error: unsupported pipeline {pipeline!r}")


def run_unicode_job(context, config_path, overwrite=False):
    config = load_prep_subject_job(config_path)
    return run_unicode_docx_ingest(
        context,
        config,
        ENTRY_POINT_UNICODE_DOCX_INGEST,
        overwrite,
        config_path,
        audit_enabled=False,
    )


def run_legacy_job(context, config_path, overwrite=False):
    config = load_prep_subject_job(config_path)
    return run_legacy_docx_to_unicode(
        context,
        config,
        ENTRY_POINT_LEGACY_DOCX_TO_UNICODE,
        overwrite,
        config_path,
        audit_enabled=False,
    )
