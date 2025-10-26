"""Helpers for interacting with object storage backends used by BioLabs."""

from __future__ import annotations

import hashlib
import io
import os
import re
from datetime import timedelta
from typing import Optional
from uuid import uuid4

try:
    from minio import Minio  # type: ignore
except ImportError:  # pragma: no cover - dependency optional in tests
    Minio = None  # type: ignore

# purpose: centralize object storage reads and writes for server features
# status: pilot
# related_docs: backend/app/README.md

_MINIO_CLIENT: Optional["Minio"] = None


def _get_upload_dir() -> str:
    """Return the configured upload directory, creating it when needed."""

    # purpose: resolve filesystem target for persisted artifacts
    # outputs: absolute or relative path for storing local uploads
    # status: pilot
    upload_dir = os.getenv("UPLOAD_DIR", "uploaded_files")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _ensure_minio_client() -> Optional["Minio"]:
    """Initialize and return a MinIO client when configuration is present."""

    # purpose: lazily configure object storage client for artifact persistence
    # outputs: Minio instance or None when not configured
    # status: pilot
    global _MINIO_CLIENT
    if Minio is None:
        return None
    endpoint = os.getenv("MINIO_ENDPOINT", "").strip()
    access_key = os.getenv("MINIO_ACCESS_KEY")
    secret_key = os.getenv("MINIO_SECRET_KEY")
    bucket = os.getenv("MINIO_BUCKET", "uploads")
    if not endpoint or not access_key or not secret_key:
        return None
    if _MINIO_CLIENT is None:
        client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=endpoint.startswith("https"),
        )
        try:
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
        except Exception:
            # Defer error handling to callers when requests fail
            return None
        _MINIO_CLIENT = client
    return _MINIO_CLIENT


def _build_object_name(namespace: str | None, filename: str) -> str:
    """Construct a normalized storage object key within an optional namespace."""

    # purpose: enforce deterministic naming for stored artifacts across backends
    # inputs: namespace path fragment and raw filename
    # outputs: sanitized object key safe for filesystem and S3 storage
    # status: pilot
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", filename) or "artifact.bin"
    if not namespace:
        return f"{uuid4()}_{safe_name}"
    clean_namespace = re.sub(r"[^A-Za-z0-9/_.-]", "_", namespace).strip("/")
    return f"{clean_namespace}/{uuid4()}_{safe_name}"


def save_binary_payload(
    data: bytes,
    filename: str,
    *,
    content_type: str = "application/octet-stream",
    namespace: str | None = None,
    encrypt: bool = False,
) -> tuple[str, int]:
    """Persist binary data using configured storage backend."""

    # purpose: write generated artifacts to durable storage
    # inputs: binary payload, logical filename, optional MIME type
    # outputs: tuple of storage path identifier and payload size in bytes
    # status: pilot
    object_suffix = _build_object_name(namespace, filename)
    client = _ensure_minio_client()
    if client:
        bucket = os.getenv("MINIO_BUCKET", "uploads")
        extra_headers = None
        if encrypt:
            extra_headers = {"X-Amz-Server-Side-Encryption": "AES256"}
        client.put_object(
            bucket,
            object_suffix,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
            metadata=extra_headers,
        )
        return f"s3://{bucket}/{object_suffix}", len(data)

    upload_dir = _get_upload_dir()
    if namespace:
        namespace_dir = os.path.join(upload_dir, *namespace.strip("/").split("/"))
        os.makedirs(namespace_dir, exist_ok=True)
        storage_path = os.path.join(namespace_dir, os.path.basename(object_suffix))
    else:
        storage_path = os.path.join(upload_dir, os.path.basename(object_suffix))
    with open(storage_path, "wb") as handle:
        handle.write(data)
    return storage_path, len(data)


def load_binary_payload(storage_path: str) -> bytes:
    """Retrieve binary data from object storage, returning raw bytes."""

    # purpose: load persisted artifacts regardless of backend implementation
    # inputs: storage locator string persisted in database metadata
    # outputs: binary payload
    # status: pilot
    if storage_path.startswith("s3://"):
        client = _ensure_minio_client()
        if not client:
            raise FileNotFoundError("Object storage client unavailable for s3 path")
        _, bucket, *key_parts = storage_path.split("/", 3)
        if not key_parts:
            raise FileNotFoundError("Invalid s3 storage path")
        object_name = key_parts[-1]
        response = client.get_object(bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    with open(storage_path, "rb") as handle:
        return handle.read()


def generate_signed_download_url(storage_path: str, expires_in: int = 3600) -> str:
    """Produce a signed URL for downloading stored artifacts when supported."""

    # purpose: safely expose time-bound download access for stored artifacts
    # inputs: persisted storage path and expiration window in seconds
    # outputs: signed URL string or direct storage path when signing unavailable
    # status: pilot
    if storage_path.startswith("s3://"):
        client = _ensure_minio_client()
        if not client:
            raise FileNotFoundError("Object storage client unavailable for presigned URL")
        _, bucket, *key_parts = storage_path.split("/", 3)
        object_name = key_parts[-1] if key_parts else ""
        if not object_name:
            raise FileNotFoundError("Invalid s3 storage path for presigned URL")
        return client.presigned_get_object(bucket, object_name, expires=timedelta(seconds=expires_in))
    return storage_path


def validate_checksum(storage_path: str, expected_checksum: str, algorithm: str = "sha256") -> bool:
    """Verify stored artifact integrity by comparing the computed checksum."""

    # purpose: detect tampering or drift of stored artifacts during lifecycle audits
    # inputs: storage locator, expected checksum string, hashing algorithm identifier
    # outputs: boolean result of checksum comparison
    # status: pilot
    data = load_binary_payload(storage_path)
    hasher = hashlib.new(algorithm)
    hasher.update(data)
    return hasher.hexdigest() == expected_checksum
