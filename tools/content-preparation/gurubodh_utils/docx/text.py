import re
import zipfile
from xml.etree import ElementTree as ET

from gurubodh_utils.docx.namespaces import NS, W
from gurubodh_utils.text_utils import normalize_spaces


def iter_docx_text_parts(zip_file):
    fixed_names = {
        "word/document.xml",
        "word/footnotes.xml",
        "word/endnotes.xml",
        "word/comments.xml",
    }
    for info in zip_file.infolist():
        name = info.filename
        if name in fixed_names or re.fullmatch(r"word/(header|footer)\d+\.xml", name):
            yield name


def paragraph_text(paragraph):
    return "".join(node.text or "" for node in paragraph.findall(".//w:t", NS))


def block_text(block):
    if block.tag != W + "p":
        return ""
    return paragraph_text(block)


def extract_text_from_xml_part(xml_bytes):
    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for paragraph in root.findall(".//w:p", NS):
        text = normalize_spaces(paragraph_text(paragraph))
        if text:
            paragraphs.append(text)
    return paragraphs


def extract_docx_text(path):
    extracted = []
    with zipfile.ZipFile(path) as source:
        for part_name in iter_docx_text_parts(source):
            extracted.extend(extract_text_from_xml_part(source.read(part_name)))
    return "\n\n".join(extracted)

