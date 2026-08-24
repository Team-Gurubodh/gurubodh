import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath


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
CANONICAL_ARTIFACT_DIRS = (
    Path("full_subject"),
    Path("chapters") / "msword",
    Path("chapters") / "text_and_metadata",
)
PROOFREADING_ARTIFACT_DIR = Path("chapters") / "proofreading"
PREP_ARTIFACT_DIRS = (*CANONICAL_ARTIFACT_DIRS, PROOFREADING_ARTIFACT_DIR)
CANONICAL_ARTIFACT_FILES = (Path("chapters") / "chapter_content_manifest.json",)
SEMANTIC_ARTIFACT_DIR = Path("chapters") / "semantic_chunks"
LEGACY_SEMANTIC_ARTIFACT_DIR = Path("chapters") / "semantic_chunks_and_embeddings"
PREP_REPORT_DIR = Path("run_reports") / "prep-subject"
CHUNKS_REPORT_DIR = Path("run_reports") / "generate-chunks"


def owned_relative_paths(command):
    if command == "prep-subject":
        return (*PREP_ARTIFACT_DIRS, *CANONICAL_ARTIFACT_FILES, PREP_REPORT_DIR)
    if command == "generate-chunks":
        return (SEMANTIC_ARTIFACT_DIR, CHUNKS_REPORT_DIR)
    raise ValueError(f"Unknown artifact owner: {command}")


def replaceable_relative_paths(command):
    """Paths that participate in preflight and overwrite; reports are append-only history."""
    if command == "prep-subject":
        return (*PREP_ARTIFACT_DIRS, *CANONICAL_ARTIFACT_FILES)
    if command == "generate-chunks":
        return (SEMANTIC_ARTIFACT_DIR,)
    raise ValueError(f"Unknown artifact owner: {command}")


def owned_prefixes(config, command):
    return [destination_object_key(config, path) + ("/" if path.suffix == "" else "") for path in replaceable_relative_paths(command)]


def r2_existing_artifacts_error(command, bucket, keys, artifact_label):
    locations = "\n".join(f"- r2://{bucket}/{key}" for key in keys)
    if command == "prep-subject":
        overwrite_effect = (
            "With --overwrite, contents of these locations will be replaced and existing semantic chunk artifacts "
            "will be invalidated. Audit history will be preserved. Unrelated subject files will be preserved.\n\n"
            "Run gurubodh generate-chunks --config <generate-chunks-job> before relying on RAG/chunk outputs."
        )
    elif command == "generate-chunks":
        overwrite_effect = (
            "With --overwrite, only semantic chunk artifacts will be replaced.\n"
            "Canonical prepared content, prep audit history, and unrelated subject files will be preserved."
        )
    else:
        raise ValueError(f"Unknown artifact owner: {command}")
    return (
        f"R2 destination already contains {artifact_label}.\n\n"
        "Re-run with --overwrite to continue:\n"
        f"{locations}\n\n{overwrite_effect}"
    )


def remove_local_owned_paths(subject_dir, command):
    removed = []
    for relative_path in replaceable_relative_paths(command):
        target = Path(subject_dir) / relative_path
        if target.is_dir():
            shutil.rmtree(target)
            removed.append(str(relative_path))
        elif target.exists():
            target.unlink()
            removed.append(str(relative_path))
    return removed


def local_owned_paths_exist(subject_dir, command):
    return [str(path) for path in replaceable_relative_paths(command) if (Path(subject_dir) / path).exists()]


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
        raise SystemExit(f"Missing Cloudflare R2 environment variables: {names}")
    return values


class R2StorageClient:
    def __init__(self, account_id, access_key_id, secret_access_key):
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError as exc:
            raise SystemExit(
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
        for index in range(0, len(keys), 1000):
            batch = keys[index : index + 1000]
            if not batch:
                continue
            self.client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": key} for key in batch]},
            )
        return keys

    def download_file(self, bucket, key, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self.client.download_file(bucket, key, str(path))
        except self._client_error as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise SystemExit(
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


def destination_subject_prefix(config):
    destination = config["destination"]
    return join_key(destination["prefix"], destination["subject_dir"]) + "/"


def subject_output_root(config):
    destination = config["destination"]
    if is_local(destination):
        return Path(destination["root_dir"]).expanduser() / destination["subject_dir"]
    temp_dir = tempfile.TemporaryDirectory(prefix="gurubodh-content-")
    return Path(temp_dir.name) / destination["subject_dir"], temp_dir


def local_source_path(config):
    source = config["source"]
    root_dir = Path(source["root_dir"]).expanduser()
    relative_path = Path(source["relative_path"])
    if relative_path.is_absolute():
        raise SystemExit("Config error: source.relative_path must be relative to source.root_dir")
    return root_dir / relative_path


def materialize_source(config, r2_client=None):
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


def ensure_local_destination(subject_dir, overwrite, command="prep-subject"):
    existed = subject_dir.exists()
    if subject_dir.exists() and not subject_dir.is_dir():
        raise SystemExit(f"Destination subject path exists but is not a directory: {subject_dir}")
    existing = local_owned_paths_exist(subject_dir, command)
    if existing and not overwrite:
        raise SystemExit(f"Destination already has {command}-owned artifacts. Re-run with --overwrite to replace: {subject_dir}")
    subject_dir.mkdir(parents=True, exist_ok=True)
    return {
        "path": str(subject_dir),
        "existed_before_run": existed,
        "removed_for_overwrite": False,
        "removed_paths": [],
    }


def ensure_r2_destination_available(config, overwrite, r2_client=None, command="prep-subject"):
    if not is_r2(config["destination"]):
        return {
            "status": "not_applicable",
            "skipped": True,
        }
    destination = config["destination"]
    prefixes = owned_prefixes(config, command)
    if overwrite:
        return {
            "status": "destructive_replacement_pending",
            "skipped": True,
            "reason": f"overwrite enabled; only {command}-owned paths will be replaced before upload",
            "bucket": destination["bucket"],
            "prefixes": prefixes,
        }
    client = r2_client or R2StorageClient.from_env()
    existing = [prefix for prefix in prefixes if client.prefix_has_objects(destination["bucket"], prefix)]
    if existing:
        raise SystemExit(
            r2_existing_artifacts_error(
                command, destination["bucket"], existing, f"{command} artifact locations"
            )
        )
    return {
        "status": "passed",
        "skipped": False,
        "bucket": destination["bucket"],
        "prefixes": prefixes,
    }


def iter_subject_files(subject_dir):
    return sorted(path for path in subject_dir.rglob("*") if path.is_file())


def prep_upload_groups(uploads, subject_dir):
    """Return prep artifacts in operator-facing publication order."""
    groups = {"full_subject": [], "chapters": {}, "manifest": [], "reports": [], "other": []}
    for upload in uploads:
        relative_path = upload[0].relative_to(subject_dir)
        if relative_path.parts[:1] == ("full_subject",):
            groups["full_subject"].append(upload)
        elif relative_path.parts[:2] in {("chapters", "msword"), ("chapters", "text_and_metadata")}:
            groups["chapters"].setdefault(upload[0].stem, []).append(upload)
        elif relative_path == Path("chapters") / "chapter_content_manifest.json":
            groups["manifest"].append(upload)
        elif relative_path.parts[:2] == ("run_reports", "prep-subject"):
            groups["reports"].append(upload)
        else:
            groups["other"].append(upload)

    ordered = []
    if groups["full_subject"]:
        ordered.append(("full_subject", sorted(groups["full_subject"])))
    if groups["chapters"]:
        suffix_order = {".docx": 0, ".txt": 1, ".json": 2}
        chapters = [
            (stem, sorted(files, key=lambda item: suffix_order.get(item[0].suffix, 99)))
            for stem, files in sorted(groups["chapters"].items())
        ]
        ordered.append(("chapters", chapters))
    if groups["manifest"]:
        ordered.append(("manifest", sorted(groups["manifest"])))
    if groups["reports"]:
        ordered.append(("reports", sorted(groups["reports"])))
    if groups["other"]:
        ordered.append(("other", sorted(groups["other"])))
    return ordered


def artifact_types(files):
    names = {".docx": "DOCX", ".txt": "text", ".json": "metadata"}
    suffixes = {path.suffix for path, _ in files}
    ordered = [suffix for suffix in (".docx", ".txt", ".json") if suffix in suffixes]
    ordered.extend(sorted(suffixes - set(ordered)))
    return ", ".join(names.get(suffix, suffix.lstrip(".")) for suffix in ordered)


def upload_r2_file(client, destination, path, key):
    try:
        client.upload_file(path, destination["bucket"], key)
    except Exception as exc:
        raise SystemExit(
            f"R2 upload failed for {path.name} to r2://{destination['bucket']}/{key}: {exc}"
        ) from exc


def publish_r2_destination(config, subject_dir, overwrite, r2_client=None, before_upload=None, command="prep-subject"):
    destination = config["destination"]
    client = r2_client or R2StorageClient.from_env()
    uploads = []
    for path in iter_subject_files(subject_dir):
        relative_path = path.relative_to(subject_dir)
        if not any(relative_path == owned or owned in relative_path.parents for owned in owned_relative_paths(command)):
            continue
        key = destination_object_key(config, relative_path)
        uploads.append((path, key))

    groups = prep_upload_groups(uploads, subject_dir) if command == "prep-subject" else None
    if groups:
        ordered_uploads = []
        for kind, items in groups:
            if kind == "chapters":
                for _, files in items:
                    ordered_uploads.extend(files)
            else:
                ordered_uploads.extend(items)
        uploads = ordered_uploads

    total = len(uploads)
    print(f"prepared {total} artifact file(s) for R2 upload")
    deleted_keys = []
    prefixes = owned_prefixes(config, command)
    if overwrite:
        for prefix in prefixes:
            deleted_keys.extend(client.delete_prefix(destination["bucket"], prefix))
        print(f"deleted {len(deleted_keys)} object(s) from {command}-owned R2 paths")
    else:
        print(f"checking {total} target object key(s) in r2://{destination['bucket']}/{destination['prefix']}")
        existing = []
        for _, key in uploads:
            if client.exists(destination["bucket"], key):
                existing.append(key)
        if existing:
            raise SystemExit(
                r2_existing_artifacts_error(
                    command, destination["bucket"], existing[:10], f"{command} target objects"
                )
            )

    if before_upload:
        before_upload(uploads, deleted_keys)

    if command == "prep-subject" and groups:
        print(f"Publishing {total} artifact(s) to:")
        print(f"  r2://{destination['bucket']}/{destination['prefix']}/{destination['subject_dir']}/")
        for index, (kind, items) in enumerate(groups, start=1):
            if kind == "chapters":
                file_count = sum(len(files) for _, files in items)
                print(f"[{index}/{len(groups)}] chapter artifacts: {len(items)} chapters / {file_count} files")
                for chapter_index, (stem, files) in enumerate(items, start=1):
                    for path, key in files:
                        upload_r2_file(client, destination, path, key)
                    print(f"  [{chapter_index:02d}/{len(items):02d}] {stem} ({artifact_types(files)})")
            else:
                for path, key in items:
                    upload_r2_file(client, destination, path, key)
                if kind == "full_subject":
                    print(f"[{index}/{len(groups)}] full subject: {items[0][0].stem} ({artifact_types(items)})")
                elif kind == "manifest":
                    print(f"[{index}/{len(groups)}] content manifest: chapters/chapter_content_manifest.json")
                elif kind == "reports":
                    print(f"[{index}/{len(groups)}] prep-subject audit: {', '.join(path.name for path, _ in items)}")
                else:
                    print(f"[{index}/{len(groups)}] other artifacts: {len(items)} files")
    else:
        print(f"uploading {total} artifact file(s) to r2://{destination['bucket']}/{destination['prefix']}")
        for index, (path, key) in enumerate(uploads, start=1):
            print(f"[{index}/{total}] uploading {key}")
            upload_r2_file(client, destination, path, key)
    print(f"uploaded {len(uploads)} artifact files to r2://{destination['bucket']}/{destination['prefix']}")
    return uploads
