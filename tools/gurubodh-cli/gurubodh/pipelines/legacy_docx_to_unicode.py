from gurubodh.config import validate_pipeline_matches_source
from gurubodh.constants import PIPELINE_LEGACY_DOCX_TO_UNICODE
from gurubodh.legacy.docx_converter import convert_docx, target_devanagari_font
from gurubodh.prep_subject_checkpoints import run_resumable_prep_job


def run_legacy_docx_to_unicode(context, config, entry_point, overwrite=False, config_path=None, resume=False, r2_client=None):
    validate_pipeline_matches_source(config, PIPELINE_LEGACY_DOCX_TO_UNICODE)
    font_name = target_devanagari_font()

    def prepare(source_path, output_path, progress):
        print("[prepare] Converting the legacy source DOCX to a transient Unicode working copy.")
        return convert_docx(
            source_path,
            font_name,
            context.legacy_converter,
            output_path,
            None,
            progress=progress,
        )

    return run_resumable_prep_job(
        config,
        entry_point,
        overwrite,
        resume,
        config_path,
        prepare,
        r2_client=r2_client,
    )
