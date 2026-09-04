import copy
import re
import zipfile
from xml.etree import ElementTree as ET

from gurubodh.docx.namespaces import NS, W
from gurubodh.docx.text import block_text
from gurubodh.naming import chapter_unmodified_source_filename
from gurubodh.text_utils import normalize_spaces, safe_filename


def chapter_starts(text, chapter_split, compiled_pattern=None):
    pattern = chapter_split["pattern"]
    if chapter_split.get("pattern_type") == "regex":
        runtime_pattern = compiled_pattern or re.compile(pattern)
        return runtime_pattern.search(text) is not None
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


def split_body_into_chapters(body, chapter_split, compiled_pattern=None):
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
        starts_chapter = block.tag == W + "p" and chapter_starts(
            text, chapter_split, compiled_pattern
        )
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


def split_docx_into_chapters(
    docx_path,
    chapter_split,
    unmodified_source_text_dir,
    config=None,
    progress=None,
    compiled_pattern=None,
):
    with zipfile.ZipFile(docx_path) as docx:
        document_xml = docx.read("word/document.xml")

    root = ET.fromstring(document_xml)
    body = root.find("w:body", NS)
    if body is None:
        raise RuntimeError("word/document.xml has no body")

    preface, chapters, _ = split_body_into_chapters(
        body, chapter_split, compiled_pattern
    )
    if not chapters:
        print(f"no chapters found using pattern: {chapter_split['pattern']}")
        return []

    subject_blocks = detect_subject_blocks(preface)
    unmodified_source_text_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"[split] Detected {len(chapters)} chapter(s); creating ordered "
        "unmodified-source text snapshots sequentially."
    )
    outputs = []
    for index, blocks in enumerate(chapters, start=1):
        print(f"[split {index:02d}/{len(chapters):02d}] Extracting the chapter source-text snapshot.")
        if config:
            unmodified_source_name = chapter_unmodified_source_filename(config, index)
        else:
            title = chapter_title(block_text(blocks[0]), index)
            unmodified_source_name = f"{title}_unmodified_source.txt"

        unmodified_source_path = unmodified_source_text_dir / unmodified_source_name
        text_value = chapter_text(subject_blocks + blocks)
        # This is the exact extracted text submitted to Gemini.  Canonical
        # chapter text and text-derived metadata are intentionally written only
        # after the strict proofreading response has been validated.
        unmodified_source_path.write_text(text_value + "\n", encoding="utf-8")
        if progress:
            progress(f"split {index:02d}/{len(chapters):02d}", unmodified_source_path)
        outputs.append(unmodified_source_path)

    if not progress:
        print(f"wrote {len(outputs)} unmodified chapter text files under {unmodified_source_text_dir}")
    return outputs
