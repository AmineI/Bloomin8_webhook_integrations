"""Helpers for reading parameters and uploads off an HttpRequest."""

from pathlib import PurePosixPath

import azure.functions as func


def param_flag(req: func.HttpRequest, name: str) -> bool:
    return (req.params.get(name) or "").strip().lower() in ("true", "1", "yes")


def extract_uploaded_image(req: func.HttpRequest) -> tuple[bytes, str | None]:
    """Return the posted image bytes and the client-supplied filename, if any."""
    content_type = (req.headers.get("Content-Type") or "").lower()

    if content_type.startswith("multipart/form-data"):
        uploaded = req.files.get("image")
        if uploaded is None:
            return b"", None
        return uploaded.read(), uploaded.filename

    return req.get_body(), None


def resolve_image_name(req: func.HttpRequest, uploaded_filename: str | None) -> str | None:
    name = (req.params.get("name") or "").strip()
    # PurePosixPath also strips Windows separators once backslashes are normalised.
    return name or PurePosixPath((uploaded_filename or "").replace("\\", "/")).stem or None
