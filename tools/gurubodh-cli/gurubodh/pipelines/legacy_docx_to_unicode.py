from gurubodh.config import validate_pipeline_matches_source
from gurubodh.constants import PIPELINE_LEGACY_DOCX_TO_UNICODE
from gurubodh.legacy.docx_converter import convert_docx, target_devanagari_font
from gurubodh.pipelines.common import prepare_job_output, publish_job_output, validate_and_split
from gurubodh.prep_subject_audit import PrepSubjectAuditWriter
from gurubodh.storage import is_r2


def run_legacy_docx_to_unicode(context, config, entry_point, overwrite=False, config_path=None, audit_enabled=True):
    validate_pipeline_matches_source(config, PIPELINE_LEGACY_DOCX_TO_UNICODE)
    job = prepare_job_output(config, overwrite)
    font_name = target_devanagari_font()
    result = convert_docx(
        job["source_path"],
        font_name,
        context.legacy_converter,
        job["full_docx"],
        job["full_text"],
    )
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
