import platform
import re
import zipfile
from xml.etree import ElementTree as ET

from gurubodh_utils.docx.namespaces import NS, W, XML_SPACE
from gurubodh_utils.docx.text import iter_docx_text_parts
from gurubodh_utils.legacy.converter import convert_text_groups
from gurubodh_utils.legacy.font_detection import is_legacy_font, rfonts_values, run_converter


def target_devanagari_font():
    system = platform.system()
    if system == "Darwin":
        return "Kohinoor Devanagari"
    if system == "Windows":
        return "Mangal"
    if system == "Linux":
        return "Noto Sans Devanagari"
    return "Noto Sans Devanagari"


def set_run_font(run, font_name):
    rpr = run.find("w:rPr", NS)
    if rpr is None:
        rpr = ET.Element(W + "rPr")
        run.insert(0, rpr)

    rfonts = rpr.find("w:rFonts", NS)
    if rfonts is None:
        rfonts = ET.Element(W + "rFonts")
        rpr.insert(0, rfonts)

    for name in ("ascii", "hAnsi", "cs", "eastAsia"):
        rfonts.set(W + name, font_name)


def set_paragraph_default_font(paragraph, font_name):
    rfonts = paragraph.find("w:pPr/w:rPr/w:rFonts", NS)
    if rfonts is None:
        return
    if any(is_legacy_font(value) for value in rfonts_values(rfonts)):
        for name in ("ascii", "hAnsi", "cs", "eastAsia"):
            rfonts.set(W + name, font_name)


def replace_legacy_font_references(root, font_name):
    for rfonts in root.findall(".//w:rFonts", NS):
        if any(is_legacy_font(value) for value in rfonts_values(rfonts)):
            for name in ("ascii", "hAnsi", "cs", "eastAsia"):
                rfonts.set(W + name, font_name)


def needs_preserve_space(text):
    return bool(text) and (text[0].isspace() or text[-1].isspace() or re.search(r"\s{2,}", text))


def set_text_node(text_node, text):
    text_node.text = text
    if needs_preserve_space(text):
        text_node.set(XML_SPACE, "preserve")
    elif XML_SPACE in text_node.attrib:
        del text_node.attrib[XML_SPACE]


def collect_paragraph_groups(root):
    groups = []
    for paragraph in root.findall(".//w:p", NS):
        current_converter = None
        current_runs = []
        current_text_nodes = []

        def flush_group():
            nonlocal current_converter, current_runs, current_text_nodes
            if not current_converter or not current_text_nodes:
                current_converter = None
                current_runs = []
                current_text_nodes = []
                return
            legacy_text = "".join(node.text or "" for node in current_text_nodes)
            if legacy_text:
                groups.append((current_converter, paragraph, list(current_runs), list(current_text_nodes), legacy_text))
            current_converter = None
            current_runs = []
            current_text_nodes = []

        for run in paragraph.findall("w:r", NS):
            converter = run_converter(run)
            nodes = run.findall("w:t", NS)
            if not converter or not nodes:
                flush_group()
                continue
            if current_converter and converter != current_converter:
                flush_group()
            current_converter = converter
            current_runs.append(run)
            current_text_nodes.extend(nodes)
        flush_group()
    return groups


def convert_xml_part(xml_bytes, font_name, legacy_converter):
    root = ET.fromstring(xml_bytes)
    groups = collect_paragraph_groups(root)
    converted_texts = convert_text_groups(groups, legacy_converter)

    extracted_text = []
    converted_nodes = 0
    converted_chars = 0
    converter_counts = {}

    for (converter, paragraph, runs, text_nodes, legacy_text), converted in zip(groups, converted_texts):
        set_paragraph_default_font(paragraph, font_name)
        for run in runs:
            set_run_font(run, font_name)

        set_text_node(text_nodes[0], converted)
        for node in text_nodes[1:]:
            set_text_node(node, "")

        extracted_text.append(converted)
        converted_nodes += len(text_nodes)
        converted_chars += len(legacy_text)
        converter_counts[converter] = converter_counts.get(converter, 0) + 1

    replace_legacy_font_references(root, font_name)
    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml, extracted_text, converted_nodes, converted_chars, converter_counts


def ensure_font_table(xml_bytes, font_name):
    root = ET.fromstring(xml_bytes)
    for font in root.findall("w:font", NS):
        if font.get(W + "name") == font_name:
            return xml_bytes

    font = ET.Element(W + "font", {W + "name": font_name})
    ET.SubElement(font, W + "charset", {W + "val": "00"})
    ET.SubElement(font, W + "family", {W + "val": "auto"})
    ET.SubElement(font, W + "pitch", {W + "val": "variable"})
    root.append(font)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def convert_docx(path, font_name, legacy_converter, output_path, text_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    extracted = []
    total_nodes = 0
    total_chars = 0
    converter_counts = {}

    with zipfile.ZipFile(path) as source:
        text_part_names = set(iter_docx_text_parts(source))
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename in text_part_names:
                    data, part_text, nodes, chars, counts = convert_xml_part(data, font_name, legacy_converter)
                    extracted.extend(part_text)
                    total_nodes += nodes
                    total_chars += chars
                    for converter, count in counts.items():
                        converter_counts[converter] = converter_counts.get(converter, 0) + count
                elif info.filename == "word/fontTable.xml":
                    data = ensure_font_table(data, font_name)
                target.writestr(info, data)

    text_path.write_text("\n\n".join(text for text in extracted if text.strip()) + "\n", encoding="utf-8")

    print(f"wrote {output_path}")
    print(f"wrote {text_path}")
    if converter_counts:
        summary = ", ".join(f"{name}: {count}" for name, count in sorted(converter_counts.items()))
        print(f"converter groups: {summary}")
    print(f"converted {total_nodes} text nodes ({total_chars} legacy characters)")
    return {
        "output_path": output_path,
        "text_path": text_path,
        "converter_counts": converter_counts,
        "total_nodes": total_nodes,
        "total_chars": total_chars,
    }

