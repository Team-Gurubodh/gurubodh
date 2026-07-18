import zipfile
from xml.etree import ElementTree as ET


def validate_docx(path):
    with zipfile.ZipFile(path) as docx:
        bad_file = docx.testzip()
        if bad_file:
            raise RuntimeError(f"Invalid DOCX ZIP entry: {bad_file}")
        ET.fromstring(docx.read("word/document.xml"))

