from dataclasses import dataclass
from pathlib import Path

from gurubodh_seed_data.config import load_seed_data_config


@dataclass(frozen=True)
class GlossaryPaths:
    source_key: str
    csv_input: Path
    json_output: Path


def glossary_paths(source):
    config = load_seed_data_config()
    return GlossaryPaths(
        source_key=source.key,
        csv_input=config.source_root / source.csv_path,
        json_output=config.artifact_root / source.artifact_path,
    )
