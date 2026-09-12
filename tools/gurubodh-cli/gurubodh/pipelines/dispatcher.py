from gurubodh.constants import (
    ENTRY_POINT_PREP_SUBJECT,
    PIPELINE_LEGACY_DOCX_TO_UNICODE,
    PIPELINE_UNICODE_DOCX_INGEST,
)
from gurubodh.errors import ConfigurationError
from gurubodh.contracts import PrepSubjectJob
from gurubodh.presentation import CommandPresentation
from gurubodh.pipelines.legacy_docx_to_unicode import run_legacy_docx_to_unicode
from gurubodh.pipelines.unicode_docx_ingest import run_unicode_docx_ingest


def run_prepared_job(
    context, config: PrepSubjectJob, entry_point=ENTRY_POINT_PREP_SUBJECT,
    overwrite=False, resume=False, progress=print,
):
    """Dispatch a validated job with its typed provenance, without file loading."""
    pipeline = config["pipeline"]
    presentation = CommandPresentation("prep-subject", progress)
    if pipeline == PIPELINE_UNICODE_DOCX_INGEST:
        return run_unicode_docx_ingest(
            config,
            entry_point,
            overwrite,
            resume=resume,
            context=context,
            progress=progress,
            presentation=presentation,
        )
    if pipeline == PIPELINE_LEGACY_DOCX_TO_UNICODE:
        return run_legacy_docx_to_unicode(
            context,
            config,
            entry_point,
            overwrite,
            resume=resume,
            progress=progress,
            presentation=presentation,
        )
    raise ConfigurationError(f"Config error: unsupported pipeline {pipeline!r}")
