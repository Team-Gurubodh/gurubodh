"""Explicit JSON policy inputs for tests of individual runtime collaborators."""

import json
from pathlib import Path

from gurubodh.proofreading.settings import ProofreadingSettings
from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig
from gurubodh.schema_validation import validate_component


FIXTURES = Path(__file__).parent / "fixtures/job-components"


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
