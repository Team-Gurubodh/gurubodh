"""Generate validated DOCX exports from canonical proofread chapter text."""

import hashlib
import json
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
from gurubodh.derived_artifact_lifecycle import (
    AuditResult,
    DerivedArtifactDefinition,
    SourceRelease,
    destination_subject_dir,
    run_derived_artifact_lifecycle,
)
from gurubodh.docx.export import (
    formatting_defaults,
    generated_title,
    validate_chapter_docx,
    write_chapter_docx,
)
from gurubodh.generate_docx_audit import GenerateDocxAuditWriter
from gurubodh.storage import (
    DOCX_REPORT_DIR,
    destination_artifact_reference,
)
from gurubodh.time_utils import utc_now


DOCX_RELATIVE_DIR = Path("chapters") / DOCX_OUTPUT_DIR
DOCX_MANIFEST_FILENAME = "docx_manifest.json"


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


def build_docx_manifest(context, config, candidate_manifest, chapters):
    return {
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


def validate_docx_staged_package(config, sources, chapters, staged_output, readiness_manifest):
    manifest = json.loads(Path(readiness_manifest).read_text(encoding="utf-8"))
    expected_names = {chapter["docx_filename"] for chapter in chapters}
    actual_names = {path.name for path in Path(staged_output).glob("*.docx")}
    if actual_names != expected_names:
        raise ValueError("Staged DOCX files do not exactly match the readiness manifest chapters.")
    if manifest.get("counts") != {
        "chapter_count": len(chapters),
        "docx_file_count": len(chapters),
    }:
        raise ValueError("DOCX readiness manifest counts do not match staged artifacts.")
    if manifest.get("chapters") != [
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
    ]:
        raise ValueError("DOCX readiness manifest chapter entries do not match generation results.")
    source_by_number = {source["chapter_number"]: source for source in sources}
    for chapter in chapters:
        path = Path(staged_output) / chapter["docx_filename"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != chapter["docx_sha256"]:
            raise ValueError(f"Staged DOCX checksum changed for chapter {chapter['chapter_number']}.")
        source = source_by_number[chapter["chapter_number"]]
        validate_chapter_docx(
            path,
            source["text_path"].read_text(encoding="utf-8"),
            chapter["generated_title"],
        )


class GenerateDocxWorkflow:
    def __init__(
        self,
        context,
        config,
        config_path,
        entry_point,
        overwrite,
        destination_subject,
    ):
        self.context = context
        self.config = config
        self.chapters = []
        self.audit = GenerateDocxAuditWriter(
            context,
            config_path,
            config,
            entry_point,
            overwrite,
            destination_subject,
        )

    def materialize_and_validate_source(self, r2_client, progress):
        subject, temporary, manifest = materialize_source_subject(
            self.config, "generate-docx", r2_client, progress
        )
        try:
            sources = validate_materialized_release(
                self.config,
                subject,
                manifest,
                "generate-docx",
                r2_client,
            )
        except BaseException:
            if temporary:
                temporary.cleanup()
            raise
        return SourceRelease(subject, manifest, sources, temporary)

    def generate_staged_artifacts(self, source, staged_output, progress):
        generate_docx_artifacts(
            self.config,
            source.sources,
            staged_output,
            progress,
            chapters=self.chapters,
        )
        return self.chapters

    def build_readiness_manifest(self, source, generation):
        return build_docx_manifest(
            self.context,
            self.config,
            source.candidate_manifest,
            generation,
        )

    def validate_staged_package(
        self, source, generation, staged_output, readiness_manifest
    ):
        validate_docx_staged_package(
            self.config,
            source.sources,
            generation,
            staged_output,
            readiness_manifest,
        )

    def write_audit(
        self,
        status,
        lifecycle,
        source,
        generation,
        publication,
        failure,
        announce,
    ):
        report = self.audit.write(
            status,
            source.candidate_manifest if source else None,
            generation if generation is not None else self.chapters,
            publication,
            failure=failure,
            lifecycle=lifecycle.as_dict(),
            announce=announce,
        )
        return AuditResult(report, self.audit.paths)


def run_generate_docx_job(
    context,
    config,
    entry_point=ENTRY_POINT_GENERATE_DOCX,
    overwrite=False,
    config_path=None,
    r2_client=None,
    progress=print,
):
    definition = DerivedArtifactDefinition(
        command_name="generate-docx",
        output_relative_dir=DOCX_RELATIVE_DIR,
        readiness_manifest_filename=DOCX_MANIFEST_FILENAME,
        readiness_manifest_artifact_name="DOCX manifest",
        report_relative_dir=DOCX_REPORT_DIR,
    )
    destination_subject, destination_temporary = destination_subject_dir(
        config, definition.command_name
    )
    workflow = GenerateDocxWorkflow(
        context,
        config,
        config_path,
        entry_point,
        overwrite,
        destination_subject,
    )
    lifecycle = run_derived_artifact_lifecycle(
        config,
        definition,
        workflow,
        overwrite=overwrite,
        r2_client=r2_client,
        progress=progress,
        destination_subject=destination_subject,
        destination_temporary=destination_temporary,
        source_revalidator=revalidate_source_release,
    )
    return {
        "processed_chapter_count": len(workflow.chapters),
        "docx_manifest": destination_artifact_reference(
            config, DOCX_RELATIVE_DIR / DOCX_MANIFEST_FILENAME
        ),
        "chapters": workflow.chapters,
        "publication": lifecycle.publication,
        "audit_report": lifecycle.audit_report,
        "lifecycle": lifecycle.lifecycle,
    }
