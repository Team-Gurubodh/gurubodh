from gurubodh.config import validate_pipeline_matches_source
from gurubodh.constants import PIPELINE_UNICODE_DOCX_INGEST
from gurubodh.docx.text import extract_docx_text
from gurubodh.prep_subject_checkpoints import run_resumable_prep_job
from gurubodh.presentation import CommandPresentation


def prepare_unicode_docx(path, _transient_docx_path=None, progress=None):
    text = extract_docx_text(path)

    if progress:
        progress("prepare", path)
    return {
        "output_path": path,
        "converter_counts": {},
        "total_nodes": 0,
        "total_chars": len(text),
    }


def run_unicode_docx_ingest(
    config,
    entry_point,
    overwrite=False,
    resume=False,
    r2_client=None,
    context=None,
    progress=print,
    presentation=None,
):
    validate_pipeline_matches_source(config, PIPELINE_UNICODE_DOCX_INGEST)
    presenter = presentation or CommandPresentation("prep-subject", progress)

    def prepare(path, transient_path=None, heartbeat=None):
        presenter.stage(
            "preparation",
            "reading the Unicode source DOCX for chapter detection and text extraction",
        )
        result = prepare_unicode_docx(path, transient_path, heartbeat)
        presenter.stage(
            "preparation",
            f"extracted {result['total_chars']} Unicode text characters",
        )
        return result

    return run_resumable_prep_job(
        config,
        entry_point,
        overwrite,
        resume,
        prepare,
        r2_client=r2_client,
        context=context,
        progress=progress,
        presentation=presenter,
    )
