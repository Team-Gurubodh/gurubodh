import json
import shutil
import subprocess


def required_command(name):
    if shutil.which(name):
        return
    raise SystemExit(f"Missing required command: {name}")


def postprocess_unicode_text(text, converter="aps"):
    if converter == "aps":
        text = text.replace("वैâ", "कै")
    text = text.replace(" ।", "।")
    return text


def convert_texts(texts, converter, legacy_converter):
    if not texts:
        return []
    required_command("node")
    if not legacy_converter.exists():
        raise SystemExit(f"Missing legacy converter: {legacy_converter}")

    proc = subprocess.run(
        ["node", str(legacy_converter)],
        input=json.dumps({"converter": converter, "texts": texts}, ensure_ascii=False),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    converted = json.loads(proc.stdout)
    return [postprocess_unicode_text(text, converter) for text in converted]


def convert_text_groups(groups, legacy_converter):
    converted = [None] * len(groups)
    by_converter = {}
    for index, group in enumerate(groups):
        by_converter.setdefault(group[0], []).append((index, group[4]))
    for converter, indexed_texts in by_converter.items():
        indexes = [index for index, _ in indexed_texts]
        texts = [text for _, text in indexed_texts]
        for index, text in zip(indexes, convert_texts(texts, converter, legacy_converter)):
            converted[index] = text
    return converted

