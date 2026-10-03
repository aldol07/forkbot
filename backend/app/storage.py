"""Object storage for original uploads (and, later, extracted images).

- local: files under STORAGE_DIR (dev, tests)
- s3:    any S3-compatible bucket: Supabase Storage, Cloudflare R2, MinIO

Keys look like "{owner_id}/{bot_id}/{document_id}/original.pdf" and are built only from UUIDs
and an allow-listed extension, never from user input.
"""
import os
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from .config import get_settings


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str | None = None) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete_prefix(self, prefix: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"storage key escapes root: {key}")
        return p

    def put(self, key, data, content_type=None):
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=p.parent)  # write-then-rename: no half-written files
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, p)

    def get(self, key):
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError:
            raise FileNotFoundError(f"stored file is missing: {key}") from None

    def delete_prefix(self, prefix):
        p = self._path(prefix.rstrip("/"))
        if p == self.root:
            raise ValueError("refusing to delete the storage root")
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()


class S3Storage:
    def __init__(self, endpoint: str, region: str, bucket: str, access_key: str, secret_key: str):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.client = boto3.client(
            "s3", endpoint_url=endpoint or None, region_name=region,
            aws_access_key_id=access_key, aws_secret_access_key=secret_key,
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
        )

    def put(self, key, data, content_type=None):
        extra = {"ContentType": content_type} if content_type else {}
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)

    def get(self, key):
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"stored file is missing: {key}") from None

    def delete_prefix(self, prefix):
        if not prefix.strip("/"):
            raise ValueError("refusing to delete the whole bucket")
        pages = self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix)
        for page in pages:
            keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if keys:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": keys})


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "s3":
        return S3Storage(s.s3_endpoint, s.s3_region, s.s3_bucket, s.s3_access_key, s.s3_secret_key)
    return LocalStorage(s.storage_dir)


def document_prefix(owner_id, bot_id, document_id) -> str:
    return f"{owner_id}/{bot_id}/{document_id}/"


def bot_prefix(owner_id, bot_id) -> str:
    return f"{owner_id}/{bot_id}/"
