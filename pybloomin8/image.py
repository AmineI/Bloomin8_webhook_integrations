"""Image conversion for Bloomin8 displays."""

import logging
from io import BytesIO
from pathlib import Path
from typing import Literal

from PIL import Image, ImageOps

log = logging.getLogger(__name__)

FitMode = Literal["cover", "fit", "stretch"]


def prepare_image(path: Path, width: int, height: int, fit_mode: FitMode = "cover") -> bytes:
    """Convert an image to a baseline JPEG at the frame's exact dimensions.

    fit_mode:
      cover   – scale to fill, center-crop the overflow (default)
      fit     – scale to fit inside, pad remaining area with black
      stretch – stretch to exact dimensions, ignoring aspect ratio
    """
    with Image.open(path) as source:
        image = source.convert("RGB")

        if fit_mode == "stretch":
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        elif fit_mode == "fit":
            image = ImageOps.fit(image, (width, height), Image.Resampling.LANCZOS)
        else:  # cover
            image = ImageOps.cover(image, (width, height), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90, progressive=False)
    log.info(
        "[IMG] Prepared %s -> %dx%d JPEG (%d bytes) [%s]",
        path,
        width,
        height,
        buffer.tell(),
        fit_mode,
    )
    return buffer.getvalue()