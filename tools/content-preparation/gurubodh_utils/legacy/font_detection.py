from gurubodh_utils.docx.namespaces import NS


CONVERTER_FONT_PATTERNS = {
    "aps": (
        "aps-dv",
        "aps dv",
        "aps_dv",
        "priyanka",
        "prakash",
    ),
    "shreelipi": (
        "shreelipi",
        "shree-lipi",
        "shree lipi",
        "srilipi",
        "sri-lipi",
        "sri lipi",
        "shree-dev",
        "shreedev",
    ),
}


def detect_converter_for_font(font_name):
    normalized = (font_name or "").lower()
    for converter, patterns in CONVERTER_FONT_PATTERNS.items():
        if any(pattern in normalized for pattern in patterns):
            return converter
    return None


def is_legacy_font(font_name):
    return detect_converter_for_font(font_name) is not None


def rfonts_values(rfonts):
    if rfonts is None:
        return []
    wanted = ("ascii", "hAnsi", "cs", "eastAsia")
    values = []
    for key, value in rfonts.attrib.items():
        local_name = key.rsplit("}", 1)[-1]
        if local_name in wanted:
            values.append(value)
    return values


def run_converter(run):
    rfonts = run.find("w:rPr/w:rFonts", NS)
    for value in rfonts_values(rfonts):
        converter = detect_converter_for_font(value)
        if converter:
            return converter
    return None

