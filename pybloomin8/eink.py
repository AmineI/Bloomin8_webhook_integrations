"""E-ink oriented post-processing for frame-bound images."""

from typing import Literal, get_args

from PIL import Image, ImageEnhance, ImageFilter

EinkPreset = Literal["off", "1"]
EINK_PRESETS: tuple[EinkPreset, ...] = get_args(EinkPreset)


def optimize_for_eink(image: Image.Image, preset: EinkPreset) -> Image.Image:
    """Apply a preset tuned for reflective color e-ink displays."""
    if preset == "off":
        return image

    if preset == "1": #Still quite bad
        optimized = ImageEnhance.Brightness(image).enhance(1.18)
        optimized = ImageEnhance.Color(optimized).enhance(1.45)
        optimized = ImageEnhance.Contrast(optimized).enhance(1.14)
        return optimized.filter(ImageFilter.UnsharpMask(radius=1.1, percent=85, threshold=6))

    return image
