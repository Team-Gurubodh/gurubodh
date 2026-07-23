import copy
import json
import subprocess
from pathlib import Path

from gurubodh.time_utils import timestamp_for_filename, utc_now


REDACTED = "[redacted]"
SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "access_key",
    "secret",
    "token",
    "password",
    "credential",
)


def redact_value(key, value):
    normalized = key.lower().replace("-", "_")
    if any(part in normalized for part in SECRET_KEY_PARTS):
        return REDACTED
    if isinstance(value, dict):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    return value


def redact_mapping(data):
    return {key: redact_value(str(key), value) for key, value in data.items()}


def json_safe(data):
    if isinstance(data, Path):
        return str(data)
    if isinstance(data, dict):
        return {str(key): json_safe(value) for key, value in data.items()}
    if isinstance(data, list):
        return [json_safe(value) for value in data]
    if isinstance(data, tuple):
        return [json_safe(value) for value in data]
    return data


def git_commit_sha(path):
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def report_basename(config, command_name, timestamp=None):
    naming = config["naming"]
    run_timestamp = timestamp or timestamp_for_filename()
    return "_".join(
        [
            naming["category_code"],
            naming["subject_code"],
            naming["title_slug"],
            command_name,
            run_timestamp,
        ]
    )


def report_paths(subject_dir, basename):
    report_dir = Path(subject_dir) / "run_reports"
    return {
        "directory": report_dir,
        "json": report_dir / f"{basename}.json",
        "markdown": report_dir / f"{basename}.md",
    }


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_report(paths, report, markdown_text):
    write_json(paths["json"], report)
    write_markdown(paths["markdown"], markdown_text)
    return {
        "json": str(paths["json"]),
        "markdown": str(paths["markdown"]),
    }


class AuditReportBuilder:
    def __init__(self, command_name, entry_point, context, config_path, config, overwrite):
        self.command_name = command_name
        self.entry_point = entry_point
        self.context = context
        self.config_path = config_path
        self.config = config
        self.overwrite = overwrite
        self.timestamp = utc_now()
        self.filename_timestamp = timestamp_for_filename()

    def run_identity(self, status, error=None):
        return {
            "run_timestamp": self.timestamp,
            "command": self.command_name,
            "entry_point": self.entry_point,
            "config_path": str(self.config_path),
            "job_schema_version": self.config.get("schema_version"),
            "pipeline": self.config.get("pipeline"),
            "source_backend": self.config["source"].get("backend", "local"),
            "destination_backend": self.config["destination"].get("backend", "local"),
            "overwrite": self.overwrite,
            "git_commit_sha": git_commit_sha(self.context.root),
            "status": status,
            "error": error,
        }

    def safe_config_snapshot(self):
        snapshot = {
            "schema_version": self.config.get("schema_version"),
            "pipeline": self.config.get("pipeline"),
            "source": copy.deepcopy(self.config.get("source", {})),
            "destination": copy.deepcopy(self.config.get("destination", {})),
            "chapter_split": {
                key: value
                for key, value in self.config.get("chapter_split", {}).items()
                if not key.startswith("_")
            },
            "metadata_defaults": copy.deepcopy(self.config.get("metadata_defaults", {})),
        }
        return redact_mapping(snapshot)
