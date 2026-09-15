"""IFC file storage on Cloudinary.

Replaces the old behaviour of writing uploads into a local UPLOAD_DIR. The
raw bytes never touch the app's disk as "stored" data — they go straight to
Cloudinary and only the resulting secure URL is persisted (on `Project.ifc_url`).

IfcOpenShell's parser only accepts a filesystem path, so `download_to_tempfile`
exists purely to hand the parser a short-lived, auto-cleaned-up working copy
when parsing happens from a Cloudinary URL (the Celery path). That temp file
is never treated as storage: nothing else reads it and it is deleted as soon
as parsing finishes.
"""
from __future__ import annotations

import logging
import tempfile
import urllib.request
import uuid

from app.core.config import settings

logger = logging.getLogger(__name__)


class CloudStorageError(RuntimeError):
    pass


def _configure() -> None:
    import cloudinary

    if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )
        return
    if settings.CLOUDINARY_URL:
        cloudinary.config(cloudinary_url=settings.CLOUDINARY_URL)
        return
    raise CloudStorageError(
        "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY "
        "and CLOUDINARY_API_SECRET (or CLOUDINARY_URL) in the environment."
    )


def upload_ifc_bytes(data: bytes, filename: str) -> str:
    """Upload raw IFC bytes to Cloudinary and return the secure URL.

    Raises CloudStorageError if Cloudinary isn't configured or the upload
    fails — callers should surface this as a real error rather than silently
    falling back to disk, since disk storage is what we're replacing.
    """
    _configure()
    import cloudinary.uploader
    from cloudinary.exceptions import Error as CloudinaryError

    public_id = f"ifc/{uuid.uuid4()}-{filename or 'model.ifc'}"
    try:
        result = cloudinary.uploader.upload(
            data,
            resource_type="raw",
            public_id=public_id,
            overwrite=False,
        )
    except CloudinaryError as exc:
        raise CloudStorageError(f"Cloudinary upload failed: {exc}") from exc
    url = result.get("secure_url")
    if not url:
        raise CloudStorageError("Cloudinary upload returned no URL.")
    logger.info("Uploaded %s to Cloudinary as %s", filename, public_id)
    return url


def download_to_tempfile(url: str) -> str:
    """Fetch a Cloudinary-hosted IFC file into a local temp path for parsing.

    The caller is responsible for deleting the returned path once parsing
    is done (mirrors how the old disk-path flow was cleaned up).
    """
    fd, path = tempfile.mkstemp(suffix=".ifc")
    try:
        with urllib.request.urlopen(url) as resp, open(fd, "wb") as out:  # noqa: S310
            out.write(resp.read())
    except Exception as exc:  # noqa: BLE001
        try:
            import os

            os.unlink(path)
        except Exception:
            pass
        raise CloudStorageError(f"Could not download IFC from Cloudinary: {exc}") from exc
    return path
