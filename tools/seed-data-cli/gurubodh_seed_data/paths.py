from dataclasses import dataclass
from pathlib import Path

from gurubodh_seed_data.config import load_seed_data_config


@dataclass(frozen=True)
class SeedDataPaths:
    source_key: str
    csv_input: Path
    json_output: Path


def seed_data_paths(source):
    config = load_seed_data_config()
    return SeedDataPaths(
        source_key=source.key,
        csv_input=config.source_root / source.csv_path,
        json_output=config.artifact_root / source.artifact_path,
    )


def glossary_paths(source):
    return seed_data_paths(source)


def category_paths(source):
    return seed_data_paths(source)


def subject_paths(source):
    return seed_data_paths(source)
