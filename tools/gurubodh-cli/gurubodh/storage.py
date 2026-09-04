import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from gurubodh.contracts import R2Downloader, R2Uploader
from gurubodh.errors import ConfigurationError, SourceValidationError, StorageError


LOCAL_BACKEND = "local"
R2_BACKEND = "r2"
R2_ENV_VARS = (
    "CLOUDFLARE_R2_ACCOUNT_ID",
    "CLOUDFLARE_R2_ACCESS_KEY_ID",
    "CLOUDFLARE_R2_SECRET_ACCESS_KEY",
)

# Artifact ownership is deliberately expressed as relative subject paths.  No
# command owns the subject root: this keeps independently-produced artifacts
# (and their audit history) safe during overwrite operations.
CANONICAL_ARTIFACT_DIRS = (Path("chapters") / "text_and_metadata",)
UNMODIFIED_SOURCE_TEXT_ARTIFACT_DIR = Path("chapters") / "unmodified_source_text"
PROOFREADING_ARTIFACT_DIR = Path("chapters") / "proofreading"
PREP_ARTIFACT_DIRS = (
    *CANONICAL_ARTIFACT_DIRS,
    UNMODIFIED_SOURCE_TEXT_ARTIFACT_DIR,
    PROOFREADING_ARTIFACT_DIR,
)
CANONICAL_ARTIFACT_FILES = (Path("chapters") / "chapter_content_manifest.json",)
DERIVED_CHAPTER_DOCX_ARTIFACT_DIR = Path("chapters") / "msword"
LEGACY_FULL_SUBJECT_ARTIFACT_DIR = Path("full_subject")
SEMANTIC_ARTIFACT_DIR = Path("chapters") / "semantic_chunks"
LEGACY_SEMANTIC_ARTIFACT_DIR = Path("chapters") / "semantic_chunks_and_embeddings"
CHUNKS_REPORT_DIR = Path("run_reports") / "generate-chunks"
DOCX_REPORT_DIR = Path("run_reports") / "generate-docx"


def replaceable_relative_paths(command):
    """Paths that participate in preflight and overwrite; reports are append-only history."""
    if command == "prep-subject":
        return (*PREP_ARTIFACT_DIRS, *CANONICAL_ARTIFACT_FILES)
    if command == "generate-chunks":
        return (SEMANTIC_ARTIFACT_DIR,)
    if command == "generate-docx":
        return (DERIVED_CHAPTER_DOCX_ARTIFACT_DIR,)
    raise ValueError(f"Unknown artifact owner: {command}")


def preflight_relative_paths(command):
    """Return paths that require an explicit overwrite before mutation.

    The legacy full-subject path is no longer prep-owned, but a successful new
    prep release must remove it. Its presence therefore still requires the
    operator's explicit ``--overwrite`` authorization.
    """
    paths = replaceable_relative_paths(command)
    if command == "prep-subject":
        return (*paths, LEGACY_FULL_SUBJECT_ARTIFACT_DIR)
    return paths


def r2_existing_artifacts_error(command, bucket, keys, artifact_label):
    locations = "\n".join(f"- r2://{bucket}/{key}" for key in keys)
    if command == "prep-subject":
        overwrite_effect = (
            "With --overwrite, prep-owned text/provenance artifacts will be replaced; same-release chapter DOCX "
            "and semantic chunk artifacts will be invalidated; and legacy full_subject artifacts will be removed. "
            "Audit history and unrelated subject files will be preserved.\n\n"
            "Run gurubodh generate-chunks --config <generate-chunks-job> before relying on RAG/chunk outputs."
        )
    elif command == "generate-chunks":
        overwrite_effect = (
            "With --overwrite, only semantic chunk artifacts will be replaced.\n"
            "Canonical prepared content, prep audit history, and unrelated subject files will be preserved."
        )
    elif command == "generate-docx":
        overwrite_effect = (
            "With --overwrite, only chapters/msword/ will be replaced.\n"
            "Canonical prepared content, semantic chunks, audit history, and unrelated subject files will be preserved."
        )
    else:
        raise ValueError(f"Unknown artifact owner: {command}")
    return (
        f"R2 destination already contains {artifact_label}.\n\n"
        "Re-run with --overwrite to continue:\n"
        f"{locations}\n\n{overwrite_effect}"
    )


def _remove_local_artifact_path(subject_dir, relative_path, reason):
    target = Path(subject_dir) / relative_path
    deleted_paths = []
    if target.is_dir():
        deleted_paths = [str(path.relative_to(subject_dir)) for path in target.rglob("*") if path.is_file()]
        shutil.rmtree(target)
    elif target.exists():
        deleted_paths = [str(target.relative_to(subject_dir))]
        target.unlink()
    return {
        "invalidated": bool(deleted_paths),
        "deleted_paths": deleted_paths,
        "path": str(relative_path),
        "reason": reason if deleted_paths else "no artifacts existed",
    }


def invalidate_local_chapter_docx_artifacts(subject_dir):
    return _remove_local_artifact_path(
        subject_dir,
        DERIVED_CHAPTER_DOCX_ARTIFACT_DIR,
        "canonical text was overwritten",
    )


def cleanup_local_legacy_full_subject(subject_dir):
    return _remove_local_artifact_path(
        subject_dir,
        LEGACY_FULL_SUBJECT_ARTIFACT_DIR,
        "the text-only prep artifact contract was published",
    )


def invalidate_local_semantic_artifacts(subject_dir):
    targets = [Path(subject_dir) / path for path in (SEMANTIC_ARTIFACT_DIR, LEGACY_SEMANTIC_ARTIFACT_DIR)]
    if not any(target.exists() for target in targets):
        return {"invalidated": False, "deleted_paths": [], "reason": "no semantic artifacts existed"}
    deleted = []
    for target in targets:
        if target.is_dir():
            deleted.extend(str(path.relative_to(subject_dir)) for path in target.rglob("*") if path.is_file())
            shutil.rmtree(target)
        elif target.exists():
            deleted.append(str(target.relative_to(subject_dir)))
            target.unlink()
    return {"invalidated": True, "deleted_paths": deleted, "reason": "canonical content was overwritten"}


def invalidate_r2_semantic_artifacts(config, r2_client=None):
    destination = config["destination"]
    prefixes = [
        destination_object_key(config, SEMANTIC_ARTIFACT_DIR) + "/",
        destination_object_key(config, LEGACY_SEMANTIC_ARTIFACT_DIR) + "/",
    ]
    client = r2_client or R2StorageClient.from_env()
    deleted = [key for prefix in prefixes for key in client.delete_prefix(destination["bucket"], prefix)]
    return {"invalidated": bool(deleted), "deleted_keys": deleted, "prefixes": prefixes,
            "reason": "canonical content was overwritten" if deleted else "no semantic artifacts existed"}


def _cleanup_r2_artifact_prefix(config, relative_path, reason, r2_client=None):
    destination = config["destination"]
    client = r2_client or R2StorageClient.from_env()
    prefix = destination_object_key(config, relative_path) + "/"
    deleted = client.delete_prefix(destination["bucket"], prefix)
    return {
        "invalidated": bool(deleted),
        "deleted_keys": deleted,
        "prefix": prefix,
        "reason": reason if deleted else "no artifacts existed",
    }


def invalidate_r2_chapter_docx_artifacts(config, r2_client=None):
    return _cleanup_r2_artifact_prefix(
        config,
        DERIVED_CHAPTER_DOCX_ARTIFACT_DIR,
        "canonical text was overwritten",
        r2_client,
    )


def cleanup_r2_legacy_full_subject(config, r2_client=None):
    return _cleanup_r2_artifact_prefix(
        config,
        LEGACY_FULL_SUBJECT_ARTIFACT_DIR,
        "the text-only prep artifact contract was published",
        r2_client,
    )


def storage_backend(config_section):
    return config_section.get("backend", LOCAL_BACKEND)


def is_local(config_section):
    return storage_backend(config_section) == LOCAL_BACKEND


def is_r2(config_section):
    return storage_backend(config_section) == R2_BACKEND


def clean_key_part(value):
    return str(PurePosixPath(str(value).strip("/")))


def join_key(*parts):
    cleaned = [clean_key_part(part) for part in parts if str(part).strip("/")]
    return "/".join(cleaned)


def optional_url(url_base, key):
    if not url_base:
        return None
    return f"{url_base.rstrip('/')}/{key}"


def require_r2_env():
    values = {name: os.environ.get(name) for name in R2_ENV_VARS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        names = ", ".join(missing)
        raise ConfigurationError(f"Missing Cloudflare R2 environment variables: {names}")
    return values


class R2StorageClient:
    def __init__(self, account_id, access_key_id, secret_access_key):
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError as exc:
            raise ConfigurationError(
                "R2 storage requires boto3. Install Gurubodh CLI dependencies with pip install -e ."
            ) from exc

        self._client_error = ClientError
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    @classmethod
    def from_env(cls):
        values = require_r2_env()
        return cls(
            values["CLOUDFLARE_R2_ACCOUNT_ID"],
            values["CLOUDFLARE_R2_ACCESS_KEY_ID"],
            values["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
        )

    def exists(self, bucket, key):
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except self._client_error as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def prefix_has_objects(self, bucket, prefix):
        response = self.client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
        return response.get("KeyCount", 0) > 0

    def list_keys(self, bucket, prefix):
        keys = []
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        while True:
            response = self.client.list_objects_v2(**kwargs)
            keys.extend(item["Key"] for item in response.get("Contents", []))
            if not response.get("IsTruncated"):
                return sorted(keys)
            kwargs["ContinuationToken"] = response["NextContinuationToken"]

    def upload_file(self, path, bucket, key):
        self.client.upload_file(str(path), bucket, key)

    def delete_prefix(self, bucket, prefix):
        keys = self.list_keys(bucket, prefix)
        self.delete_keys(bucket, keys)
        return keys

    def delete_keys(self, bucket, keys):
        for index in range(0, len(keys), 1000):
            batch = keys[index : index + 1000]
            if not batch:
                continue
            self.client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": key} for key in batch]},
            )
        return list(keys)

    def download_file(self, bucket, key, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self.client.download_file(bucket, key, str(path))
        except self._client_error as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise SourceValidationError(
                    "R2 source object does not exist. Check the job source key or upload the source DOCX:\n"
                    f"r2://{bucket}/{key}"
                ) from exc
            raise


def source_reference(config):
    source = config["source"]
    backend = storage_backend(source)
    if backend == LOCAL_BACKEND:
        return {
            "backend": LOCAL_BACKEND,
            "path": str(source["relative_path"]),
            "url": None,
        }
    key = source["key"]
    return {
        "backend": R2_BACKEND,
        "bucket": source["bucket"],
        "key": key,
        "url": optional_url(source.get("url_base"), key),
    }


def destination_artifact_reference(config, relative_path):
    destination = config["destination"]
    backend = storage_backend(destination)
    if backend == LOCAL_BACKEND:
        return {
            "backend": LOCAL_BACKEND,
            "path": str(relative_path),
            "url": None,
        }
    key = join_key(destination["prefix"], destination["subject_dir"], relative_path.as_posix())
    return {
        "backend": R2_BACKEND,
        "bucket": destination["bucket"],
        "key": key,
        "url": optional_url(destination.get("url_base"), key),
    }


def destination_object_key(config, relative_path):
    destination = config["destination"]
    return join_key(destination["prefix"], destination["subject_dir"], relative_path.as_posix())


def subject_artifact_prefix(section):
    return join_key(section["prefix"], section["subject_dir"]) + "/"


def subject_artifact_object_key(section, relative_path):
    return join_key(section["prefix"], section["subject_dir"], relative_path.as_posix())


def local_source_path(config):
    source = config["source"]
    root_dir = Path(source["root_dir"]).expanduser()
    relative_path = Path(source["relative_path"])
    if relative_path.is_absolute():
        raise ConfigurationError("Config error: source.relative_path must be relative to source.root_dir")
    return root_dir / relative_path


def materialize_source(config, r2_client: R2Downloader | None = None):
    source = config["source"]
    if is_local(source):
        path = local_source_path(config)
        return path, None

    temp_dir = tempfile.TemporaryDirectory(prefix="gurubodh-source-")
    filename = PurePosixPath(source["key"]).name
    path = Path(temp_dir.name) / filename
    client = r2_client or R2StorageClient.from_env()
    print(f"downloading R2 source r2://{source['bucket']}/{source['key']}")
    client.download_file(source["bucket"], source["key"], path)
    return path, temp_dir


def upload_r2_file(client: R2Uploader, destination, path: Path, key: str) -> None:
    try:
        client.upload_file(path, destination["bucket"], key)
    except Exception as exc:
        raise StorageError(
            f"R2 upload failed for {path.name} to r2://{destination['bucket']}/{key}: {exc}"
        ) from exc
