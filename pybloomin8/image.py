"""Image conversion for Bloomin8 displays."""

import logging
from io import BytesIO
from typing import Literal, get_args

from PIL import Image, ImageOps

from . import effects

log = logging.getLogger(__name__)

DisplayMode = Literal[
    "cover",
    "fit",
    "pad",
    "border-color-pad",
    "gradient-pad",
    "gradient-popout",
    "vibrant-popout",
    "blur-pad",
    "blur-popout",
]
DISPLAY_MODES: tuple[DisplayMode, ...] = get_args(DisplayMode)


def prepare_image(
    image_data: bytes, width: int, height: int, display_mode: DisplayMode = "cover"
) -> bytes:
    """Convert encoded image data to a PNG sized for the frame.

    display_mode:
    https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#resize-relative-to-a-given-size
      cover   – scale until the panel is covered, keeping the aspect ratio; the
                overflowing dimension is left for the frame to crop (default)
      fit     – scale and center-crop to exactly width x height
      pad     – scale until the image fits within dimensions, keeping the aspect ratio;
                the remaining space around is left blank (letterboxing)
      Added effects :
      - border-color-pad: pad, with the empty space filled with the image's average
                border colour
      - gradient-pad: pad, with the empty space filled with a gradient between the four
                dominant colours of the image
      - gradient-popout: gradient-pad, with the image floating with a margin, rounded
                corners and a soft drop shadow
      - vibrant-popout: the image floats with a margin over a backdrop built from the
                artwork's most vibrant colours, with rounded corners and a soft drop shadow
      - blur-pad: pad, with the empty space filled with a blurred enlargement of
                the image itself
      - blur-popout: the image floats with a margin over a blurred, muted enlargement of
                the image itself, with rounded corners and a soft drop shadow
    """
    with Image.open(BytesIO(image_data)) as opened:
        image = opened.convert("RGB")

        if display_mode == "cover":
            image = ImageOps.cover(image, (width, height), Image.Resampling.LANCZOS)
        elif display_mode == "fit":
            image = ImageOps.fit(image, (width, height), Image.Resampling.LANCZOS)
        elif display_mode == "pad":
            image = ImageOps.pad(image, (width, height), Image.Resampling.LANCZOS, color="white")
        elif display_mode == "border-color-pad":
            image = ImageOps.pad(
                image, (width, height),
                Image.Resampling.LANCZOS,
                color=effects.border_color(image),
            )
        elif display_mode == "gradient-pad":
            image = effects.center_on(image, effects.gradient_backdrop(image, width, height))
        elif display_mode == "gradient-popout":
            image = effects.popout_on(image, effects.gradient_backdrop(image, width, height))
        elif display_mode == "vibrant-popout":
            image = effects.popout_on(image, effects.vibrant_backdrop(image, width, height))
        elif display_mode == "blur-pad":
            image = effects.center_on(image, effects.blurred_backdrop(image, width, height))
        elif display_mode == "blur-popout":
            image = effects.popout_on(
                image, effects.color_wash_backdrop(image, width, height))
        else:
            raise ValueError(f"Unsupported display_mode: {display_mode}")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    log.info(
        "[IMG] Prepared %d bytes -> %dx%d PNG (%d bytes) [%s]",
        len(image_data),
        width,
        height,
        buffer.tell(),
        display_mode,
    )
    return buffer.getvalue()