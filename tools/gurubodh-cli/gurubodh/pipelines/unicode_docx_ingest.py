import shutil

from gurubodh.config import validate_pipeline_matches_source
from gurubodh.constants import PIPELINE_UNICODE_DOCX_INGEST
from gurubodh.docx.text import extract_docx_text
from gurubodh.pipelines.common import prepare_job_output, publish_job_output, validate_and_split
from gurubodh.prep_subject_audit import PrepSubjectAuditWriter
from gurubodh.storage import is_r2


def copy_unicode_docx(path, output_path, text_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(path, output_path)
    text = extract_docx_text(output_path)
    text_path.write_text((text + "\n") if text else "", encoding="utf-8")

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


def run_unicode_docx_ingest(context, config, entry_point, overwrite=False, config_path=None, audit_enabled=True):
    validate_pipeline_matches_source(config, PIPELINE_UNICODE_DOCX_INGEST)
    job = prepare_job_output(config, overwrite)
    result = copy_unicode_docx(job["source_path"], job["full_docx"], job["full_text"])
    split_outputs = validate_and_split(config, result, job["paths"], entry_point)
    if audit_enabled:
        audit = PrepSubjectAuditWriter(context, config_path, config, entry_point, overwrite, job, result, split_outputs)
        if is_r2(config["destination"]):
            audit.write_r2_pending()
            publish_job_output(config, job, overwrite, before_upload=audit.before_r2_upload)
        else:
            audit.write_local_success()
            publish_job_output(config, job, overwrite)
    else:
        publish_job_output(config, job, overwrite)
    return result
