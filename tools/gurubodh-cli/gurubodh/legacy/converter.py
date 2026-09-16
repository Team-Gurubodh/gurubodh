import json
import re
import shutil
import subprocess

from gurubodh.errors import ConfigurationError, ProcessingError
from gurubodh.resource_discovery import bundled_resource_path


SUPPORTED_NODE_MAJORS = (22, 24)
NODE_GUIDANCE = (
    "Install Node.js 22 or 24 from https://nodejs.org/en/download and ensure "
    "the 'node' executable is on PATH. Then run 'gurubodh aps check'."
)


def check_node():
    node = shutil.which("node")
    if node is None:
        raise ConfigurationError(f"Node.js is required for APS conversion. {NODE_GUIDANCE}")
    try:
        result = subprocess.run(
            [node, "--version"], text=True, capture_output=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ConfigurationError(f"Could not run node --version: {exc}. {NODE_GUIDANCE}") from exc
    version = result.stdout.strip()
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version)
    if match is None:
        raise ConfigurationError(f"Unrecognized Node.js version {version!r}. {NODE_GUIDANCE}")
    if int(match.group(1)) not in SUPPORTED_NODE_MAJORS:
        raise ConfigurationError(
            f"Incompatible Node.js version {version}; APS conversion supports Node.js 22 or 24. "
            f"{NODE_GUIDANCE}"
        )
    return node, version


def check_aps_conversion():
    """Exercise the bundled converter with one pinned APS mapping vector."""
    actual = convert_texts(["efkeâ&"], "aps", bundled_resource_path("scripts/legacy_font_convert.js"))
    expected = ["र्कि"]
    if actual != expected:
        raise ProcessingError(f"APS diagnostic failed: expected {expected!r}, got {actual!r}.")
    return actual[0]


def postprocess_unicode_text(text, converter="aps"):
    if converter == "aps":
        text = text.replace("वैâ", "कै")
    text = text.replace(" ।", "।")
    return text


def convert_texts(texts, converter, legacy_converter):
    if not texts:
        return []
    node, _ = check_node()
    if not legacy_converter.exists():
        raise ConfigurationError(f"Missing legacy converter: {legacy_converter}")

    try:
        proc = subprocess.run(
            [node, str(legacy_converter)],
            input=json.dumps({"converter": converter, "texts": texts}, ensure_ascii=False),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or "Node produced no error output."
        raise ProcessingError(
            f"Legacy font converter {converter!r} failed (exit {exc.returncode}; "
            f"script: {legacy_converter}). Node stderr:\n{detail}"
        ) from exc
    except OSError as exc:
        raise ProcessingError(f"Could not run APS converter with Node.js: {exc}") from exc
    try:
        converted = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ProcessingError("APS converter returned invalid JSON output.") from exc
    if not isinstance(converted, list) or len(converted) != len(texts) or any(
        not isinstance(item, str) for item in converted
    ):
        raise ProcessingError("APS converter returned an unexpected conversion result.")
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
