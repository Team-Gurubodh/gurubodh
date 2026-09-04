"""Canonical prep publication and post-publication overwrite cleanup."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Protocol

from gurubodh.contracts import PrepSubjectJob, R2Client
from gurubodh.prep_metrics import PrepMetrics
from gurubodh.storage import (
    CANONICAL_ARTIFACT_FILES,
    PREP_ARTIFACT_DIRS,
    cleanup_local_legacy_full_subject,
    cleanup_r2_legacy_full_subject,
    destination_object_key,
    invalidate_local_chapter_docx_artifacts,
    invalidate_local_semantic_artifacts,
    invalidate_r2_chapter_docx_artifacts,
    invalidate_r2_semantic_artifacts,
)


class PrepPublisher(Protocol):
    """Publication strategy independent of checkpoint persistence."""

    def publish_canonical(
        self, workspace_dir: Path, overwrite: bool
    ) -> dict[str, Any]: ...

    def invalidate_chapter_docx(self) -> dict[str, Any]: ...

    def cleanup_legacy_full_subject(self) -> dict[str, Any]: ...

    def invalidate_semantic_artifacts(self) -> dict[str, Any]: ...


class LocalPrepPublisher:
    def __init__(self, subject_dir: Path) -> None:
        self.subject_dir = subject_dir

    def publish_canonical(
        self, workspace_dir: Path, overwrite: bool
    ) -> dict[str, Any]:
        del overwrite
        promotion_root = workspace_dir / ".promotion"
        backup_root = workspace_dir / ".publication-backup"
        for relative in PREP_ARTIFACT_DIRS:
            source = workspace_dir / relative
            if source.exists():
                self._replace_path(
                    source,
                    self.subject_dir / relative,
                    relative,
                    promotion_root,
                    backup_root,
                )
        # The candidate manifest is the downstream readiness marker and is last.
        for relative in CANONICAL_ARTIFACT_FILES:
            source = workspace_dir / relative
            if source.exists():
                self._replace_path(
                    source,
                    self.subject_dir / relative,
                    relative,
                    promotion_root,
                    backup_root,
                )
        return {}

    @staticmethod
    def _replace_path(
        source: Path,
        target: Path,
        relative: Path,
        promotion_root: Path,
        backup_root: Path,
    ) -> None:
        candidate = promotion_root / relative
        candidate.parent.mkdir(parents=True, exist_ok=True)
        if candidate.is_dir():
            shutil.rmtree(candidate)
        elif candidate.exists():
            candidate.unlink()
        if source.is_dir():
            shutil.copytree(source, candidate)
        else:
            shutil.copy2(source, candidate)
        if target.exists():
            backup = backup_root / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            if backup.is_dir():
                shutil.rmtree(backup)
            elif backup.exists():
                backup.unlink()
            shutil.move(str(target), str(backup))
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(candidate, target)

    def invalidate_chapter_docx(self) -> dict[str, Any]:
        return invalidate_local_chapter_docx_artifacts(self.subject_dir)

    def cleanup_legacy_full_subject(self) -> dict[str, Any]:
        return cleanup_local_legacy_full_subject(self.subject_dir)

    def invalidate_semantic_artifacts(self) -> dict[str, Any]:
        return invalidate_local_semantic_artifacts(self.subject_dir)


class R2PrepPublisher:
    def __init__(
        self,
        config: PrepSubjectJob,
        client: R2Client,
        metrics: PrepMetrics,
    ) -> None:
        self.config = config
        self.destination = config["destination"]
        self.client = client
        self.metrics = metrics

    def publish_canonical(
        self, workspace_dir: Path, overwrite: bool
    ) -> dict[str, Any]:
        uploads: list[tuple[Path, str]] = []
        manifest_relative = Path("chapters") / "chapter_content_manifest.json"
        for relative in (*PREP_ARTIFACT_DIRS, *CANONICAL_ARTIFACT_FILES):
            root = workspace_dir / relative
            if root.is_file():
                uploads.append(
                    (root, destination_object_key(self.config, relative))
                )
            elif root.is_dir():
                uploads.extend(
                    (
                        path,
                        destination_object_key(
                            self.config, path.relative_to(workspace_dir)
                        ),
                    )
                    for path in sorted(root.rglob("*"))
                    if path.is_file()
                )
        uploads.sort(
            key=lambda item: item[0].relative_to(workspace_dir)
            == manifest_relative
        )
        for path, key in uploads:
            self.metrics.upload(
                self.client,
                self.destination,
                path,
                key,
                category="canonical_publication_artifacts",
            )

        if overwrite:
            stale_keys: list[str] = []
            uploaded_keys = {key for _, key in uploads}
            for relative in PREP_ARTIFACT_DIRS:
                prefix = destination_object_key(self.config, relative) + "/"
                stale_keys.extend(
                    key
                    for key in self.client.list_keys(
                        self.destination["bucket"], prefix
                    )
                    if key not in uploaded_keys
                )
            self.client.delete_keys(self.destination["bucket"], stale_keys)
            return {
                "stale_prep_artifact_cleanup": {
                    "deleted_keys": stale_keys,
                    "deleted_count": len(stale_keys),
                }
            }
        return {}

    def invalidate_chapter_docx(self) -> dict[str, Any]:
        return invalidate_r2_chapter_docx_artifacts(self.config, self.client)

    def cleanup_legacy_full_subject(self) -> dict[str, Any]:
        return cleanup_r2_legacy_full_subject(self.config, self.client)

    def invalidate_semantic_artifacts(self) -> dict[str, Any]:
        return invalidate_r2_semantic_artifacts(self.config, self.client)


def create_prep_publisher(
    config: PrepSubjectJob,
    subject_dir: Path,
    metrics: PrepMetrics,
    client: R2Client | None,
) -> PrepPublisher:
    if client is not None:
        return R2PrepPublisher(config, client, metrics)
    return LocalPrepPublisher(subject_dir)
