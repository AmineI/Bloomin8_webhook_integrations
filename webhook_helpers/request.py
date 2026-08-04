"""Helpers for reading query parameters and uploads off webhook requests."""

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Protocol


class UploadedFile(Protocol):
    filename: str

    def read(self) -> bytes: ...


class UploadedFiles(Protocol):
    def get(self, name: str) -> UploadedFile | None: ...


class UploadRequest(Protocol):
    headers: Mapping[str, str]
    files: UploadedFiles

    def get_body(self) -> bytes: ...


def param_flag(params: Mapping[str, str], name: str) -> bool:
    return (params.get(name) or "").strip().lower() in ("true", "1", "yes")


def extract_uploaded_image(req: UploadRequest) -> tuple[bytes, str | None]:
    """Return the posted image bytes and the client-supplied filename, if any."""
    content_type = (req.headers.get("Content-Type") or "").lower()

    if content_type.startswith("multipart/form-data"):
        uploaded = req.files.get("image")
        if uploaded is None:
            return b"", None
        return uploaded.read(), uploaded.filename

    return req.get_body(), None


def resolve_image_name(params: Mapping[str, str], uploaded_filename: str | None) -> str | None:
    name = (params.get("name") or "").strip()
    # PurePosixPath also strips Windows separators once backslashes are normalised.
    return name or PurePosixPath((uploaded_filename or "").replace("\\", "/")).stem or None
