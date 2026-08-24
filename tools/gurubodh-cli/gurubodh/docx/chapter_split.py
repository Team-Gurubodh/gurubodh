import copy
import re
import zipfile
from xml.etree import ElementTree as ET

from gurubodh.docx.namespaces import NS, W
from gurubodh.docx.text import block_text
from gurubodh.docx.validate import validate_docx
from gurubodh.naming import chapter_output_filename, chapter_unmodified_source_filename
from gurubodh.text_utils import normalize_spaces, safe_filename


def chapter_starts(text, chapter_split):
    pattern = chapter_split["pattern"]
    if chapter_split.get("pattern_type") == "regex":
        return chapter_split["_compiled_pattern"].search(text) is not None
    return pattern in text


def is_invocation(text):
    return "श्री स्वामी" in text or "जय जय" in text


def detect_subject_blocks(blocks):
    candidates = []
    for block in blocks[:8]:
        text = normalize_spaces(block_text(block))
        if not text:
            continue
        if "विषय" in text:
            return [copy.deepcopy(block)]
        candidates.append((block, text))

    for block, text in candidates:
        if is_invocation(text) or "प्रबोधन क्र" in text:
            continue
        return [copy.deepcopy(block)]
    return []


def chapter_title(text, index):
    text = normalize_spaces(text)
    match = re.search(r"प्रबोधन\s+क्र\.?\s*([^\s]+)", text)
    if match:
        return f"{index:03d}-प्रबोधन-क्र-{safe_filename(match.group(1))}"
    return f"{index:03d}-{safe_filename(text)}"


def chapter_text(blocks):
    parts = []
    for block in blocks:
        text = normalize_spaces(block_text(block))
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def split_body_into_chapters(body, chapter_split):
    children = list(body)
    sect_pr = None
    content_blocks = []
    for child in children:
        if child.tag == W + "sectPr":
            sect_pr = child
        else:
            content_blocks.append(child)

    chapters = []
    preface = []
    current = None
    for block in content_blocks:
        text = block_text(block)
        starts_chapter = block.tag == W + "p" and chapter_starts(text, chapter_split)
        if starts_chapter:
            if current:
                chapters.append(current)
            current = [block]
        elif current is None:
            preface.append(block)
        else:
            current.append(block)

    if current:
        chapters.append(current)

    return preface, chapters, sect_pr


def chapter_document_xml(document_xml, chapter_blocks, subject_blocks, sect_pr):
    root = ET.fromstring(document_xml)
    body = root.find("w:body", NS)
    if body is None:
        raise RuntimeError("word/document.xml has no body")

    for child in list(body):
        body.remove(child)

    for block in subject_blocks:
        body.append(copy.deepcopy(block))
    for block in chapter_blocks:
        body.append(copy.deepcopy(block))
    if sect_pr is not None:
        body.append(copy.deepcopy(sect_pr))

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_chapter_docx(source_docx, output_path, document_xml):
    with zipfile.ZipFile(source_docx) as source:
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                data = document_xml if info.filename == "word/document.xml" else source.read(info.filename)
                target.writestr(info, data)


def split_docx_into_chapters(
    docx_path,
    chapter_split,
    chapter_docx_dir,
    unmodified_source_text_dir,
    config=None,
    progress=None,
):
    with zipfile.ZipFile(docx_path) as docx:
        document_xml = docx.read("word/document.xml")

    root = ET.fromstring(document_xml)
    body = root.find("w:body", NS)
    if body is None:
        raise RuntimeError("word/document.xml has no body")

    preface, chapters, sect_pr = split_body_into_chapters(body, chapter_split)
    if not chapters:
        print(f"no chapters found using pattern: {chapter_split['pattern']}")
        return []

    subject_blocks = detect_subject_blocks(preface)
    chapter_docx_dir.mkdir(parents=True, exist_ok=True)
    unmodified_source_text_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"[split] Detected {len(chapters)} chapter(s); creating chapter DOCX files "
        "and unmodified-source snapshots sequentially."
    )
    outputs = []
    for index, blocks in enumerate(chapters, start=1):
        print(f"[split {index:02d}/{len(chapters):02d}] Starting chapter DOCX split and source-text extraction.")
        if config:
            docx_name = chapter_output_filename(config, index, ".docx")
            unmodified_source_name = chapter_unmodified_source_filename(config, index)
        else:
            title = chapter_title(block_text(blocks[0]), index)
            docx_name = f"{title}.docx"
            unmodified_source_name = f"{title}_unmodified_source.txt"

        output_path = chapter_docx_dir / docx_name
        unmodified_source_path = unmodified_source_text_dir / unmodified_source_name
        xml = chapter_document_xml(document_xml, blocks, subject_blocks, sect_pr)
        write_chapter_docx(docx_path, output_path, xml)
        text_value = chapter_text(subject_blocks + blocks)
        # This is the exact extracted text submitted to Gemini.  Canonical
        # chapter text and text-derived metadata are intentionally written only
        # after the strict proofreading response has been validated.
        unmodified_source_path.write_text(text_value + "\n", encoding="utf-8")
        validate_docx(output_path)
        if progress:
            progress(f"split {index:02d}/{len(chapters):02d}", output_path, unmodified_source_path)
        outputs.append(output_path)

    if not progress:
        print(f"wrote {len(outputs)} chapter files under {chapter_docx_dir}")
        print(f"wrote {len(outputs)} unmodified chapter text files under {unmodified_source_text_dir}")
    return outputs
