from gurubodh_utils.config import validate_pipeline_matches_source
from gurubodh_utils.constants import PIPELINE_LEGACY_DOCX_TO_UNICODE
from gurubodh_utils.legacy.docx_converter import convert_docx, target_devanagari_font
from gurubodh_utils.pipelines.common import (
    prepare_job_output,
    publish_job_output,
    validate_and_split,
    write_job_run_reports,
)


def run_legacy_docx_to_unicode(context, config, entry_point, config_path, overwrite=False):
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
    validate_and_split(config, result, job["paths"], entry_point)
    write_job_run_reports(config, job, result, entry_point, config_path, overwrite, context.root)
    publish_job_output(config, job, overwrite)
    return result
