from dataclasses import dataclass
from pathlib import Path


SEED_DATA_ROOT = Path(__file__).resolve().parents[1]
GLOSSARY_SOURCE_DIR = Path("sources") / "glossary"
GLOSSARY_ARTIFACT_DIR = Path("artifacts") / "glossary"


@dataclass(frozen=True)
class GlossaryPaths:
    source_key: str
    csv_input: Path
    json_output: Path


def glossary_paths(source):
    return GlossaryPaths(
        source_key=source.key,
        csv_input=GLOSSARY_SOURCE_DIR / source.csv_filename,
        json_output=GLOSSARY_ARTIFACT_DIR / source.json_filename,
    )


def resolve_seed_data_path(path):
    return SEED_DATA_ROOT / path
