import shutil

from gurubodh_utils.config import validate_pipeline_matches_source
from gurubodh_utils.constants import PIPELINE_UNICODE_DOCX_INGEST
from gurubodh_utils.docx.text import extract_docx_text
from gurubodh_utils.pipelines.common import prepare_job_output, publish_job_output, validate_and_split


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


def run_unicode_docx_ingest(context, config, entry_point, overwrite=False):
    validate_pipeline_matches_source(config, PIPELINE_UNICODE_DOCX_INGEST)
    job = prepare_job_output(config, overwrite)
    result = copy_unicode_docx(job["source_path"], job["full_docx"], job["full_text"])
    validate_and_split(config, result, job["paths"], entry_point)
    publish_job_output(config, job, overwrite)
    return result
