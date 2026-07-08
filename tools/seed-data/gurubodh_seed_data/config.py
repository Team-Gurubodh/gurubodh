import json
from dataclasses import dataclass
from pathlib import Path


SEED_DATA_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = SEED_DATA_ROOT / "config" / "seed_data_sources.json"


@dataclass(frozen=True)
class SeedDataWorkflow:
    key: str
    status: str
    description: str


@dataclass(frozen=True)
class SeedDataSource:
    key: str
    workflow: str
    label: str
    csv_path: Path
    artifact_path: Path


@dataclass(frozen=True)
class SeedDataConfig:
    schema_version: int
    source_root: Path
    artifact_root: Path
    workflows: tuple[SeedDataWorkflow, ...]
    sources: tuple[SeedDataSource, ...]

    def sources_for_workflow(self, workflow_key):
        return tuple(
            source for source in self.sources
            if source.workflow == workflow_key
        )

    def get_source(self, workflow_key, source_key):
        for source in self.sources_for_workflow(workflow_key):
            if source.key == source_key:
                return source

        accepted_values = ", ".join(
            source.key for source in self.sources_for_workflow(workflow_key)
        )
        raise ValueError(
            f"Unsupported {workflow_key} source: {source_key}\n"
            f"Accepted values: {accepted_values}"
        )


def _require_object(data, field_name):
    value = data.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"Seed-data config field must be a list: {field_name}")
    return value


def _require_text(data, field_name):
    value = data.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Seed-data config field must be a non-empty string: {field_name}")
    return value


def _ensure_unique(values, value_type):
    seen = set()
    for value in values:
        if value in seen:
            raise ValueError(f"Duplicate seed-data {value_type}: {value}")
        seen.add(value)


def load_seed_data_config(config_path=None):
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with path.open(encoding="utf-8") as config_file:
        data = json.load(config_file)

    schema_version = data.get("schema_version")
    if schema_version != 1:
        raise ValueError(
            "Unsupported seed-data config schema_version: "
            f"{schema_version!r}"
        )

    source_root = Path(_require_text(data, "source_root"))
    artifact_root = Path(_require_text(data, "artifact_root"))
    if not artifact_root.is_absolute():
        artifact_root = SEED_DATA_ROOT / artifact_root

    workflow_records = _require_object(data, "workflows")
    workflows = tuple(
        SeedDataWorkflow(
            key=_require_text(record, "key"),
            status=_require_text(record, "status"),
            description=_require_text(record, "description"),
        )
        for record in workflow_records
    )
    _ensure_unique((workflow.key for workflow in workflows), "workflow key")

    workflow_keys = {workflow.key for workflow in workflows}
    source_records = _require_object(data, "sources")
    sources = []
    for record in source_records:
        workflow = _require_text(record, "workflow")
        if workflow not in workflow_keys:
            raise ValueError(
                "Seed-data source references an unsupported workflow: "
                f"{workflow}"
            )
        sources.append(
            SeedDataSource(
                key=_require_text(record, "key"),
                workflow=workflow,
                label=_require_text(record, "label"),
                csv_path=Path(_require_text(record, "csv_path")),
                artifact_path=Path(_require_text(record, "artifact_path")),
            )
        )
    sources = tuple(sources)
    _ensure_unique((source.key for source in sources), "source key")

    return SeedDataConfig(
        schema_version=schema_version,
        source_root=source_root,
        artifact_root=artifact_root,
        workflows=workflows,
        sources=sources,
    )
