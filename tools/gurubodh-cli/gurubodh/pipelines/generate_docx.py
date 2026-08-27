"""Generate validated DOCX exports from canonical proofread chapter text."""

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from gurubodh import __version__
from gurubodh.audit import resolved_build_provenance
from gurubodh.canonical_source import (
    materialize_source_subject,
    revalidate_source_release,
    validate_materialized_release,
)
from gurubodh.constants import (
    DOCX_FORMATTING_CONTRACT_VERSION,
    DOCX_MANIFEST_SCHEMA_VERSION,
    DOCX_OUTPUT_DIR,
    DOCX_TITLE_TEMPLATE_ID,
    DOCX_TITLE_TEMPLATE_VERSION,
    ENTRY_POINT_GENERATE_DOCX,
)
from gurubodh.docx.export import formatting_defaults, generated_title, write_chapter_docx
from gurubodh.generate_docx_audit import GenerateDocxAuditWriter
from gurubodh.storage import (
    DOCX_REPORT_DIR,
    R2StorageClient,
    destination_artifact_reference,
    is_local,
    is_r2,
    r2_existing_artifacts_error,
    subject_artifact_object_key,
    upload_r2_file,
)
from gurubodh.time_utils import utc_now


DOCX_RELATIVE_DIR = Path("chapters") / DOCX_OUTPUT_DIR
DOCX_MANIFEST_FILENAME = "docx_manifest.json"


def destination_subject_dir(config):
    destination = config["destination"]
    if is_local(destination):
        return Path(destination["root_dir"]).expanduser() / destination["subject_dir"], None
    temp_dir = tempfile.TemporaryDirectory(prefix="gurubodh-generate-docx-destination-")
    return Path(temp_dir.name) / destination["subject_dir"], temp_dir


def destination_docx_prefix(config):
    if not is_r2(config["destination"]):
        return None
    return subject_artifact_object_key(config["destination"], DOCX_RELATIVE_DIR) + "/"


def preflight_destination(config, destination_subject, overwrite, r2_client=None):
    output_dir = Path(destination_subject) / DOCX_RELATIVE_DIR
    destination = config["destination"]
    if is_local(destination):
        exists = output_dir.exists()
        if exists and not overwrite:
            raise SystemExit(
                f"DOCX output already exists. Re-run with --overwrite to replace only: {output_dir}"
            )
        return {
            "backend": "local",
            "status": "passed",
            "path": str(output_dir),
            "existed_before_run": exists,
            "overwrite_requested": overwrite,
        }
    client = r2_client or R2StorageClient.from_env()
    prefix = destination_docx_prefix(config)
    exists = client.prefix_has_objects(destination["bucket"], prefix)
    if exists and not overwrite:
        raise SystemExit(
            r2_existing_artifacts_error(
                "generate-docx", destination["bucket"], [prefix], "generate-docx output"
            )
        )
    return {
        "backend": "r2",
        "status": "passed",
        "bucket": destination["bucket"],
        "prefix": prefix,
        "existed_before_run": exists,
        "overwrite_requested": overwrite,
    }


def _docx_filename(source):
    filename = source["text_path"].name
    if Path(filename).suffix != ".txt":
        raise SystemExit(f"Canonical source text filename must end in .txt: {filename}")
    return str(Path(filename).with_suffix(".docx"))


def generate_docx_artifacts(config, sources, output_dir, progress=print, chapters=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    chapters = chapters if chapters is not None else []
    for index, source in enumerate(sources, start=1):
        chapter_number = source["chapter_number"]
        filename = _docx_filename(source)
        title = generated_title(config["naming"]["title_slug"], chapter_number)
        path = output_dir / filename
        metadata = source["metadata"]
        summary = {
            "chapter_number": chapter_number,
            "content_key": metadata["content_identity"]["content_key"],
            "normalized_content_sha256": metadata["content_identity"]["normalized_content_sha256"],
            "source_text": {
                "reference": source["text_artifact"],
                "sha256": source["text_artifact_sha256"],
            },
            "generated_title": title,
            "docx_filename": filename,
            "docx_artifact": destination_artifact_reference(config, DOCX_RELATIVE_DIR / filename),
            "docx_sha256": None,
            "status": "running",
            "error": None,
        }
        chapters.append(summary)
        progress(f"[{index:02d}/{len(sources):02d}] chapter {chapter_number}: generating {filename}")
        try:
            text = source["text_path"].read_text(encoding="utf-8")
            write_chapter_docx(path, text, title, config["naming"]["language"])
            summary["docx_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            summary["status"] = "succeeded"
        except Exception as exc:
            summary["status"] = "failed"
            summary["error"] = str(exc)[:500] or exc.__class__.__name__
            raise
        progress(f"[{index:02d}/{len(sources):02d}] chapter {chapter_number}: validated")
    return chapters


def write_docx_manifest(path, context, config, candidate_manifest, chapters):
    payload = {
        "schema_version": DOCX_MANIFEST_SCHEMA_VERSION,
        "formatting_contract_version": DOCX_FORMATTING_CONTRACT_VERSION,
        "created_at": utc_now(),
        "command": {
            "pipeline": "generate-docx",
            "package_version": __version__,
            "build_provenance": resolved_build_provenance(context.root),
        },
        "subject": {key: config["naming"][key] for key in ("category_code", "subject_code", "title_slug", "language")},
        "source_candidate_manifest": {
            "reference": candidate_manifest["reference"],
            "sha256": candidate_manifest["sha256"],
        },
        "formatting": formatting_defaults(),
        "title_template": {
            "id": DOCX_TITLE_TEMPLATE_ID,
            "version": DOCX_TITLE_TEMPLATE_VERSION,
            "template": "<title_slug>: prabodhan <chapter_number>",
        },
        "counts": {"chapter_count": len(chapters), "docx_file_count": len(chapters)},
        "chapters": [
            {
                key: chapter[key]
                for key in (
                    "chapter_number",
                    "content_key",
                    "normalized_content_sha256",
                    "source_text",
                    "generated_title",
                    "docx_artifact",
                    "docx_sha256",
                )
            }
            for chapter in chapters
        ],
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def publish_local(staged_output, destination_output, overwrite):
    destination_output = Path(destination_output)
    destination_output.parent.mkdir(parents=True, exist_ok=True)
    if destination_output.exists() and not overwrite:
        raise SystemExit(
            f"DOCX output appeared after preflight. Re-run with --overwrite only after inspecting: {destination_output}"
        )
    incoming = destination_output.with_name(f".{destination_output.name}.incoming-{uuid.uuid4().hex}")
    backup = destination_output.with_name(f".{destination_output.name}.backup-{uuid.uuid4().hex}")
    replaced = False
    try:
        shutil.copytree(staged_output, incoming)
        if destination_output.exists():
            os.replace(destination_output, backup)
            replaced = True
        os.replace(incoming, destination_output)
    except Exception:
        if replaced and backup.exists() and not destination_output.exists():
            os.replace(backup, destination_output)
        raise
    finally:
        if incoming.exists():
            shutil.rmtree(incoming)
        if backup.exists():
            if backup.is_dir():
                shutil.rmtree(backup)
            else:
                backup.unlink()
    return {
        "backend": "local",
        "status": "succeeded",
        "output_path": str(destination_output),
        "replaced_existing_output": replaced,
    }


def publish_r2(
    config, staged_output, overwrite, r2_client=None, progress=print, publication_audit=None
):
    destination = config["destination"]
    client = r2_client or R2StorageClient.from_env()
    audit = publication_audit if publication_audit is not None else {}
    prefix = destination_docx_prefix(config)
    manifest_key = subject_artifact_object_key(destination, DOCX_RELATIVE_DIR / DOCX_MANIFEST_FILENAME)
    if not overwrite and client.prefix_has_objects(destination["bucket"], prefix):
        raise SystemExit(
            r2_existing_artifacts_error(
                "generate-docx", destination["bucket"], [prefix], "generate-docx output that appeared after preflight"
            )
        )
    deleted = []
    audit.update(
        {
            "backend": "r2",
            "status": "publishing",
            "bucket": destination["bucket"],
            "prefix": prefix,
            "deleted_for_overwrite": deleted,
            "uploaded_keys": [],
            "manifest_published_last": False,
        }
    )
    if overwrite:
        if client.exists(destination["bucket"], manifest_key):
            deleted.extend(client.delete_keys(destination["bucket"], [manifest_key]))
        deleted.extend(client.delete_prefix(destination["bucket"], prefix))
    docx_files = sorted(Path(staged_output).glob("*.docx"), key=lambda path: path.name)
    progress(f"Publishing {len(docx_files)} validated DOCX file(s) to r2://{destination['bucket']}/{prefix}")
    uploads = []
    for index, path in enumerate(docx_files, start=1):
        key = subject_artifact_object_key(destination, DOCX_RELATIVE_DIR / path.name)
        upload_r2_file(client, destination, path, key)
        uploads.append(key)
        audit["uploaded_keys"].append(key)
        progress(f"[{index:02d}/{len(docx_files):02d}] uploaded {path.name}")
    manifest_path = Path(staged_output) / DOCX_MANIFEST_FILENAME
    upload_r2_file(client, destination, manifest_path, manifest_key)
    uploads.append(manifest_key)
    audit["uploaded_keys"].append(manifest_key)
    audit["manifest_published_last"] = True
    audit["status"] = "succeeded"
    progress("Published docx_manifest.json last; the DOCX export set is ready.")
    return dict(audit)


def _upload_audit_reports(config, audit, r2_client):
    destination = config["destination"]
    for kind in ("json", "markdown"):
        path = audit.paths[kind]
        key = subject_artifact_object_key(destination, DOCX_REPORT_DIR / path.name)
        upload_r2_file(r2_client, destination, path, key)


def run_generate_docx_job(
    context,
    config,
    entry_point=ENTRY_POINT_GENERATE_DOCX,
    overwrite=False,
    config_path=None,
    r2_client=None,
    progress=print,
):
    client = r2_client if (is_r2(config["source"]) or is_r2(config["destination"])) else None
    if client is None and (is_r2(config["source"]) or is_r2(config["destination"])):
        client = R2StorageClient.from_env()
    destination_subject, destination_temp = destination_subject_dir(config)
    audit = GenerateDocxAuditWriter(
        context, config_path, config, entry_point, overwrite, destination_subject
    )
    candidate_manifest = None
    chapters = []
    source_temp = None
    publication = {"backend": config["destination"].get("backend", "local"), "status": "not_started"}
    stage = "preflight"
    with tempfile.TemporaryDirectory(prefix="gurubodh-generate-docx-stage-") as stage_dir:
        staged_output = Path(stage_dir) / DOCX_OUTPUT_DIR
        try:
            preflight = preflight_destination(config, destination_subject, overwrite, client)
            publication = {**preflight, "status": "preflight_passed"}
            stage = "source_validation"
            source_subject, source_temp, candidate_manifest = materialize_source_subject(
                config, "generate-docx", client, progress
            )
            sources = validate_materialized_release(
                config, source_subject, candidate_manifest, "generate-docx", client
            )
            stage = "generation"
            generate_docx_artifacts(
                config, sources, staged_output, progress, chapters=chapters
            )
            write_docx_manifest(
                staged_output / DOCX_MANIFEST_FILENAME,
                context,
                config,
                candidate_manifest,
                chapters,
            )
            stage = "source_revalidation"
            revalidate_source_release(config, candidate_manifest, "generate-docx", client)
            stage = "publication"
            if is_local(config["destination"]):
                publication = publish_local(
                    staged_output,
                    destination_subject / DOCX_RELATIVE_DIR,
                    overwrite,
                )
            else:
                publication = publish_r2(
                    config,
                    staged_output,
                    overwrite,
                    client,
                    progress,
                    publication_audit=publication,
                )
            stage = "audit"
            report = audit.write(
                "succeeded",
                candidate_manifest,
                chapters,
                publication,
                announce=is_local(config["destination"]),
            )
            if is_r2(config["destination"]):
                _upload_audit_reports(config, audit, client)
                progress(
                    "Published generate-docx audit reports under "
                    f"r2://{config['destination']['bucket']}/"
                    f"{subject_artifact_object_key(config['destination'], DOCX_REPORT_DIR)}/"
                )
            return {
                "processed_chapter_count": len(chapters),
                "docx_manifest": destination_artifact_reference(
                    config, DOCX_RELATIVE_DIR / DOCX_MANIFEST_FILENAME
                ),
                "chapters": chapters,
                "publication": publication,
                "audit_report": report,
            }
        except BaseException as exc:
            failure = {"stage": stage, "message": str(exc)[:1000] or exc.__class__.__name__}
            publication = {**publication, "status": "failed"}
            try:
                audit.write(
                    "failed",
                    candidate_manifest,
                    chapters,
                    publication,
                    failure=failure,
                    announce=is_local(config["destination"]),
                )
                if is_r2(config["destination"]):
                    _upload_audit_reports(config, audit, client)
            except (Exception, SystemExit):
                pass
            raise
        finally:
            if source_temp:
                source_temp.cleanup()
            if destination_temp:
                destination_temp.cleanup()
