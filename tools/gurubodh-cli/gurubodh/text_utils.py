import re


def normalize_spaces(text):
    return re.sub(r"\s+", " ", text).strip()


def safe_filename(text):
    text = normalize_spaces(text)
    text = re.sub(r"[\\/:*?\"<>|]+", "-", text)
    text = re.sub(r"\s+", "-", text)
    text = text.strip(".-")
    return text[:80] or "chapter"

