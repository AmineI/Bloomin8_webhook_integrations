"""Image conversion for Bloomin8 displays."""

import logging
from io import BytesIO
from typing import Literal

from PIL import Image, ImageOps

log = logging.getLogger(__name__)

FitMode = Literal["cover", "fit", "stretch"]


def prepare_image(
    image_data: bytes, width: int, height: int, fit_mode: FitMode = "cover"
) -> bytes:
    """Convert encoded image data to a baseline JPEG sized for the frame.

    fit_mode:
      cover   – scale until the panel is covered, keeping the aspect ratio; the
                overflowing dimension is left for the frame to crop (default)
      fit     – scale and center-crop to exactly width x height
      stretch – stretch to exact dimensions, ignoring aspect ratio
    """
    with Image.open(BytesIO(image_data)) as opened:
        image = opened.convert("RGB")

        if fit_mode == "stretch":
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        elif fit_mode == "fit":
            image = ImageOps.fit(image, (width, height), Image.Resampling.LANCZOS)
        else:  # cover
            image = ImageOps.cover(image, (width, height), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90, progressive=False)
    log.info(
        "[IMG] Prepared %d bytes -> %dx%d JPEG (%d bytes) [%s]",
        len(image_data),
        width,
        height,
        buffer.tell(),
        fit_mode,
    )
    return buffer.getvalue()