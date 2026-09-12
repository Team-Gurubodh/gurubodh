from gurubodh.docx.chapter_split import split_docx_into_chapters
from gurubodh.docx.validate import validate_docx


def validate_and_split(config, result, paths, progress=None):
    emit = progress or print
    emit("validating the prepared source DOCX before chapter detection")
    validate_docx(result["output_path"])

    chapter_split = config["chapter_split"]
    if chapter_split.get("enabled"):
        outputs = split_docx_into_chapters(
            result["output_path"],
            chapter_split,
            paths["unmodified_source_text"],
            config,
            progress=progress,
            compiled_pattern=getattr(config, "compiled_chapter_pattern", None),
        )
        return outputs
    return []
