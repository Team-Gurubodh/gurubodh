from gurubodh.config import validate_pipeline_matches_source
from gurubodh.constants import PIPELINE_UNICODE_DOCX_INGEST
from gurubodh.docx.text import extract_docx_text
from gurubodh.prep_subject_checkpoints import run_resumable_prep_job


def prepare_unicode_docx(path, transient_docx_path=None, progress=None):
    print("[prepare] Reading the Unicode source DOCX directly for chapter detection and text extraction.")
    text = extract_docx_text(path)

    if progress:
        progress("prepare", path)
    print(f"extracted {len(text)} Unicode text characters")
    return {
        "output_path": path,
        "converter_counts": {},
        "total_nodes": 0,
        "total_chars": len(text),
    }


def run_unicode_docx_ingest(context, config, entry_point, overwrite=False, config_path=None, audit_enabled=True, resume=False, r2_client=None):
    validate_pipeline_matches_source(config, PIPELINE_UNICODE_DOCX_INGEST)
    return run_resumable_prep_job(
        context,
        config,
        entry_point,
        overwrite,
        resume,
        config_path,
        prepare_unicode_docx,
        r2_client=r2_client,
    )
