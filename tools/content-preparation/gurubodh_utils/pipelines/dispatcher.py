from gurubodh_utils.config import load_conversion_job
from gurubodh_utils.constants import (
    ENTRY_POINT_LEGACY_DOCX_TO_UNICODE,
    ENTRY_POINT_RUN,
    ENTRY_POINT_UNICODE_DOCX_INGEST,
    PIPELINE_LEGACY_DOCX_TO_UNICODE,
    PIPELINE_UNICODE_DOCX_INGEST,
)
from gurubodh_utils.pipelines.legacy_docx_to_unicode import run_legacy_docx_to_unicode
from gurubodh_utils.pipelines.unicode_docx_ingest import run_unicode_docx_ingest


def run_configured_job(context, config_path, entry_point=ENTRY_POINT_RUN, overwrite=False):
    config = load_conversion_job(config_path)
    pipeline = config["pipeline"]
    if pipeline == PIPELINE_UNICODE_DOCX_INGEST:
        return run_unicode_docx_ingest(context, config, entry_point, config_path, overwrite)
    if pipeline == PIPELINE_LEGACY_DOCX_TO_UNICODE:
        return run_legacy_docx_to_unicode(context, config, entry_point, config_path, overwrite)
    raise SystemExit(f"Config error: unsupported pipeline {pipeline!r}")


def run_unicode_job(context, config_path, overwrite=False):
    config = load_conversion_job(config_path)
    return run_unicode_docx_ingest(
        context,
        config,
        ENTRY_POINT_UNICODE_DOCX_INGEST,
        config_path,
        overwrite,
    )


def run_legacy_job(context, config_path, overwrite=False):
    config = load_conversion_job(config_path)
    return run_legacy_docx_to_unicode(
        context,
        config,
        ENTRY_POINT_LEGACY_DOCX_TO_UNICODE,
        config_path,
        overwrite,
    )
