from gurubodh.config import validate_pipeline_matches_source
from gurubodh.constants import PIPELINE_UNICODE_DOCX_INGEST
from gurubodh.docx.text import extract_docx_text
from gurubodh.prep_subject_checkpoints import run_resumable_prep_job
import shutil


def copy_unicode_docx(path, output_path, text_path, progress=None):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(path, output_path)
    text = extract_docx_text(output_path)
    text_path.write_text((text + "\n") if text else "", encoding="utf-8")

    if progress:
        progress("prepare", output_path, text_path)
    else:
        print(f"copied Unicode DOCX to {output_path}")
        print(f"wrote {text_path}")
    print(f"extracted {len(text)} Unicode text characters")
    return {
        "output_path": output_path,
        "text_path": text_path,
        "converter_counts": {},
        "total_nodes": 0,
        "total_chars": len(text),
    }


def run_unicode_docx_ingest(context, config, entry_point, overwrite=False, config_path=None, audit_enabled=True, resume=False, r2_client=None):
    validate_pipeline_matches_source(config, PIPELINE_UNICODE_DOCX_INGEST)
    print("[prepare] Copying the Unicode source DOCX and extracting full-subject text.")
    return run_resumable_prep_job(
        context,
        config,
        entry_point,
        overwrite,
        resume,
        config_path,
        copy_unicode_docx,
        r2_client=r2_client,
    )
