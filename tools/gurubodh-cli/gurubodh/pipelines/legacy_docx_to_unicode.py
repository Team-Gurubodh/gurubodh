from gurubodh.config import validate_pipeline_matches_source
from gurubodh.constants import PIPELINE_LEGACY_DOCX_TO_UNICODE
from gurubodh.legacy.docx_converter import convert_docx, target_devanagari_font
from gurubodh.prep_subject_checkpoints import run_resumable_prep_job
from gurubodh.presentation import CommandPresentation


def run_legacy_docx_to_unicode(
    context,
    config,
    entry_point,
    overwrite=False,
    resume=False,
    r2_client=None,
    progress=print,
    presentation=None,
):
    validate_pipeline_matches_source(config, PIPELINE_LEGACY_DOCX_TO_UNICODE)
    font_name = target_devanagari_font()
    presenter = presentation or CommandPresentation("prep-subject", progress)

    def prepare(source_path, output_path, heartbeat):
        presenter.stage(
            "preparation",
            "converting the legacy source DOCX to a transient Unicode working copy",
        )

        def conversion_progress(*values):
            message = ": ".join(str(value) for value in values)
            presenter.stage("preparation", message)
            heartbeat(*values)

        return convert_docx(
            source_path,
            font_name,
            context.legacy_converter,
            output_path,
            None,
            progress=conversion_progress,
        )

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
