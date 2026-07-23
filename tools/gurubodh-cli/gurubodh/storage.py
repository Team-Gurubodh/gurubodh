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

    def upload_file(self, path, bucket, key):
        self.client.upload_file(str(path), bucket, key)

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


def ensure_local_destination(subject_dir, overwrite):
    existed = subject_dir.exists()
    removed_for_overwrite = False
    if subject_dir.exists():
        if not subject_dir.is_dir():
            raise SystemExit(f"Destination subject path exists but is not a directory: {subject_dir}")
        if not overwrite:
            raise SystemExit(f"Destination already exists. Re-run with --overwrite to replace: {subject_dir}")
        shutil.rmtree(subject_dir)
        removed_for_overwrite = True
    subject_dir.mkdir(parents=True, exist_ok=True)
    return {
        "path": str(subject_dir),
        "existed_before_run": existed,
        "removed_for_overwrite": removed_for_overwrite,
    }


def ensure_r2_destination_available(config, overwrite, r2_client=None):
    if not is_r2(config["destination"]):
        return {
            "status": "not_applicable",
            "skipped": True,
        }
    destination = config["destination"]
    prefix = destination_subject_prefix(config)
    if overwrite:
        return {
            "status": "skipped",
            "skipped": True,
            "reason": "overwrite enabled",
            "bucket": destination["bucket"],
            "prefix": prefix,
        }
    client = r2_client or R2StorageClient.from_env()
    print(f"checking R2 destination prefix r2://{destination['bucket']}/{prefix}")
    if client.prefix_has_objects(destination["bucket"], prefix):
        raise SystemExit(
            "R2 destination prefix already contains objects. Re-run with --overwrite to replace:\n"
            f"r2://{destination['bucket']}/{prefix}"
        )
    return {
        "status": "passed",
        "skipped": False,
        "bucket": destination["bucket"],
        "prefix": prefix,
    }


def iter_subject_files(subject_dir):
    return sorted(path for path in subject_dir.rglob("*") if path.is_file())


def publish_r2_destination(config, subject_dir, overwrite, r2_client=None, before_upload=None):
    destination = config["destination"]
    client = r2_client or R2StorageClient.from_env()
    uploads = []
    for path in iter_subject_files(subject_dir):
        relative_path = path.relative_to(subject_dir)
        key = destination_object_key(config, relative_path)
        uploads.append((path, key))

    total = len(uploads)
    print(f"prepared {total} artifact file(s) for R2 upload")
    print(f"checking target object keys in r2://{destination['bucket']}/{destination['prefix']}")

    existing = []
    for index, (_, key) in enumerate(uploads, start=1):
        print(f"[{index}/{total}] checking {key}")
        if client.exists(destination["bucket"], key):
            existing.append(key)
    if existing and not overwrite:
        sample = "\n".join(f"- {key}" for key in existing[:10])
        extra = "" if len(existing) <= 10 else f"\n... and {len(existing) - 10} more"
        raise SystemExit(
            "R2 destination object(s) already exist. Re-run with --overwrite to replace:\n"
            f"{sample}{extra}"
        )

    if before_upload:
        before_upload(uploads)

    print(f"uploading {total} artifact file(s) to r2://{destination['bucket']}/{destination['prefix']}")
    for index, (path, key) in enumerate(uploads, start=1):
        print(f"[{index}/{total}] uploading {key}")
        client.upload_file(path, destination["bucket"], key)
    print(f"uploaded {len(uploads)} artifact files to r2://{destination['bucket']}/{destination['prefix']}")
    return uploads
