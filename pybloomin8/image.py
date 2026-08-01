"""Image conversion for Bloomin8 displays."""

import logging
from io import BytesIO
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)


def prepare_image(path: Path, width: int, height: int) -> bytes:
    """Convert an image to a baseline JPEG at the frame's exact dimensions."""
    with Image.open(path) as source:
        image = source.convert("RGB")
        # TODO : Is this really needed ? Should we offer crop, cover, or this kind of stuff ?
        #image = image.resize((width, height), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90, progressive=False)
    log.info(
        "[IMG] Prepared %s -> %dx%d JPEG (%d bytes)",
        path,
        width,
        height,
        buffer.tell(),
    )
    return buffer.getvalue()