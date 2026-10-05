"""Explicit JSON policy inputs for tests of individual runtime collaborators."""

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

from gurubodh.proofreading.settings import ProofreadingSettings
from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig
from gurubodh.schema_validation import validate_component


FIXTURES = Path(__file__).parent / "fixtures/job-components"


@contextmanager
def synthetic_source_fonts(*, fixture_root: Path = FIXTURES.parent) -> Iterator[None]:
    from gurubodh.legacy import font_detection

    original = font_detection.bundled_resource_path

    def resource(relative):
        if relative == "config/policies/source-fonts.json":
            return fixture_root / "source-fonts.json"
        return original(relative)

    with patch.object(font_detection, "bundled_resource_path", side_effect=resource):
        yield


def proofreading_settings(**changes):
    document = json.loads((FIXTURES / "proofreading/gemini-3.6-flash-v1.json").read_text())
    validate_component(document, "proofreading-profile")
    document["proofreading"].update(changes)
    return ProofreadingSettings(**{
        name: document["proofreading"][name] for name in ProofreadingSettings.__dataclass_fields__
    })


def chunking_settings(**changes):
    document = json.loads((FIXTURES / "chunking/bge-m3-semantic-window-v1.json").read_text())
    validate_component(document, "chunking-profile")
    settings = document["chunking"]
    settings["model_name"] = settings.pop("model")
    settings.update(changes)
    return SemanticChunkConfig.from_env(**settings)
