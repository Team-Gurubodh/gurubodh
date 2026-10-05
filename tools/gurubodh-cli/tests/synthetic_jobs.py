"""Independent, bounded CLI inputs; no maintained catalog or resolver imports."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any


FIXTURES = Path(__file__).parent / "fixtures/job-components"


def fixture_document(relative: str, *, fixture_root: Path = FIXTURES) -> dict[str, Any]:
    root = fixture_root.resolve()
    name = Path(relative)
    if name.is_absolute() or ".." in name.parts:
        raise ValueError("Fixture name must be contained and relative")
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Fixture path escapes fixture root")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Fixture must contain a JSON object")
    return document


def write_catalog(root: Path, *, fixture_root: Path = FIXTURES) -> None:
    def write(relative, document):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for directory in ("commands", "environments", "storage-profiles", "locales", "proofreading", "chunking"):
        paths = sorted((fixture_root / directory).glob("*.json"))
        if not paths:
            raise FileNotFoundError(f"Missing synthetic fixtures: {directory}")
        destination = f"profiles/{directory}" if directory in ("proofreading", "chunking") else directory
        for path in paths:
            write(f"config/job-components/{destination}/{path.name}",
                  fixture_document(f"{directory}/{path.name}", fixture_root=fixture_root))
    for name in ("aps-hindi", "unicode-bilingual"):
        document = fixture_document(f"subjects/{name}.json", fixture_root=fixture_root)
        write(f"jobs/subjects/{document['manifest_id']}/manifest.json", document)
    profile = fixture_document("proofreading/gemini-3.6-flash-v1.json", fixture_root=fixture_root)
    for identity, budget in (("example-proofreading-v2", 20000),
                             ("gemini-3.6-flash-large-input-v1", 40000)):
        alternate = deepcopy(profile)
        alternate["profile_id"] = identity
        alternate["proofreading"]["max_estimated_input_tokens_per_minute"] = budget
        write(f"config/job-components/profiles/proofreading/{identity}.json", alternate)


def job_payload(
    command: str, *, root: Path, manifest_id: str = "sub001_aps_example", locale: str = "hi-IN",
    storage_profile_id: str = "local", fixture_root: Path = FIXTURES,
) -> dict[str, Any]:
    """Hand-authored command/routing contracts populated only from fixture inputs.

    This intentionally does not implement general profile resolution. The
    equivalent renamed fixture profile has the same settings as the default;
    precedence tests supply their own distinct inputs and literal expectations.
    """
    manifests = {"sub001_aps_example": "aps-hindi", "sub123_spand_rahasya": "unicode-bilingual"}
    if command not in ("prep-subject", "generate-chunks", "generate-docx") or manifest_id not in manifests:
        raise ValueError("Unsupported synthetic command or manifest")
    if storage_profile_id not in ("local", "r2-output", "r2"):
        raise ValueError("Unsupported synthetic storage route")
    manifest = fixture_document(f"subjects/{manifests[manifest_id]}.json", fixture_root=fixture_root)
    if locale not in manifest["editions"]:
        raise ValueError("Unsupported synthetic edition")
    edition = manifest["editions"][locale]
    subject_dir = f"{manifest['artifact_root']}/{locale}"
    source_r2 = storage_profile_id == "r2"
    destination_r2 = storage_profile_id != "local"
    source = ({"backend": "r2", "bucket": "gurubodh-library-dev", "url_base": None}
              if source_r2 else {"backend": "local", "root_dir": str(root / (
                  "source" if command == "prep-subject" else "artifacts"))})
    destination = ({"backend": "r2", "bucket": "gurubodh-library-dev", "url_base": None,
                    "prefix": "cms_library"} if destination_r2 else
                   {"backend": "local", "root_dir": str(root / "artifacts")})
    destination["subject_dir"] = subject_dir
    naming = deepcopy(manifest["identity"])
    if command != "generate-docx":
        naming.update(edition["release"])
    if command == "prep-subject":
        declaration = edition["source_document"]
        source.update(font_encoding=declaration["font_encoding"], file_format="docx")
        source["key" if source_r2 else "relative_path"] = (
            "source_library/" if source_r2 else "") + declaration["relative_path"]
    else:
        source["subject_dir"] = subject_dir
        if source_r2:
            source["prefix"] = "cms_library"
        naming["language"] = locale
    payload = {
        "schema_version": {"prep-subject": "1.5.0", "generate-chunks": "1.2.0", "generate-docx": "1.0.0"}[command],
        "pipeline": ({"aps": "legacy-docx-to-unicode", "unicode": "unicode-docx-ingest"}[
            edition["source_document"]["font_encoding"]] if command == "prep-subject" else command),
        "source": source, "destination": destination, "naming": naming,
    }
    if command == "prep-subject":
        payload["chapter_split"] = deepcopy(edition["chapter_split"])
        payload["metadata_defaults"] = {"language": locale, **fixture_document(
            f"locales/{locale}.json", fixture_root=fixture_root)["metadata_defaults"]}
        payload["proofreading"] = fixture_document(
            "proofreading/gemini-3.6-flash-v1.json", fixture_root=fixture_root)["proofreading"]
    elif command == "generate-chunks":
        payload["chunking"] = fixture_document(
            "chunking/bge-m3-semantic-window-v1.json", fixture_root=fixture_root)["chunking"]
    return payload
