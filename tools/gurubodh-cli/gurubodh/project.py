import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectContext:
    root: Path
    legacy_converter: Path


def _looks_like_project_root(path):
    return (
        (path / "config" / "jobs" / "prep_subject_job.schema.json").is_file()
        and (path / "jobs" / "subjects").is_dir()
    )


def _find_project_root(start):
    current = start.resolve()
    for candidate in (current, *current.parents):
        if _looks_like_project_root(candidate):
            return candidate
    return None


def resolve_project_context(project_root=None):
    if project_root:
        root = Path(project_root).expanduser().resolve()
        if not _looks_like_project_root(root):
            raise SystemExit(f"Project root does not contain config/jobs/ and jobs/subjects/: {root}")
    else:
        env_root = os.environ.get("GURUBODH_CLI_ROOT")
        if env_root:
            root = Path(env_root).expanduser().resolve()
            if not _looks_like_project_root(root):
                raise SystemExit(f"GURUBODH_CLI_ROOT is not a Gurubodh CLI project root: {root}")
        else:
            root = _find_project_root(Path.cwd())
            if root is None:
                raise SystemExit(
                    "Could not find project root. Run from the project tree, set "
                    "GURUBODH_CLI_ROOT, or pass --project-root."
                )

    return ProjectContext(
        root=root,
        legacy_converter=root / "scripts" / "legacy_font_convert.js",
    )


def resolve_project_path(context, path):
    path = Path(path).expanduser()
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (context.root / path).resolve()
