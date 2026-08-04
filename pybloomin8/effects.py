"""Backdrop and foreground effects used to compose images for the frame."""

import colorsys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageStat

# Shared by the callers that lay a foreground out over a backdrop.
FOREGROUND_MARGIN_RATIO = 0.07
CORNER_RADIUS_RATIO = 0.015


def border_color(image: Image.Image) -> tuple[int, int, int]:
    """Return the average colour of the image's one-pixel outer border."""
    width, height = image.size
    strips = (
        image.crop((0, 0, width, 1)),
        image.crop((0, height - 1, width, height)),
        image.crop((0, 0, 1, height)),
        image.crop((width - 1, 0, width, height)),
    )

    channel_totals = [0.0, 0.0, 0.0]
    pixel_count = 0
    for strip in strips:
        stat = ImageStat.Stat(strip)
        channel_totals = [total + value for total, value in zip(channel_totals, stat.sum)]
        pixel_count += stat.count[0]

    red, green, blue = (int(total / pixel_count) for total in channel_totals)
    return red, green, blue


def _saturation(color: tuple[int, int, int]) -> float:
    highest, lowest = max(color), min(color)
    return 0.0 if highest == 0 else (highest - lowest) / highest


def _shade(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    red, green, blue = (min(255, round(channel * factor)) for channel in color)
    return red, green, blue


def _hls(color: tuple[int, int, int]) -> tuple[float, float, float]:
    """Return the colour's HLS hue, lightness and saturation, all on 0..1."""
    hue, lightness, saturation = colorsys.rgb_to_hls(*(channel / 255 for channel in color))
    return hue, lightness, saturation


def _hue_distance(first: float, second: float) -> float:
    """Return the shorter way round the colour wheel between two hues, on 0..0.5."""
    gap = abs(first - second) % 1.0
    return min(gap, 1.0 - gap)


def _blend(first: tuple[int, int, int], second: tuple[int, int, int]) -> tuple[int, int, int]:
    red, green, blue = ((left + right) // 2 for left, right in zip(first, second))
    return red, green, blue


def _glow_over(
    backdrop: Image.Image,
    color: tuple[int, int, int],
    opacity: int,
    center_ratio: float,
    radius_ratio: float,
) -> Image.Image:
    """Return the backdrop with a soft round bloom of colour over it."""
    width, height = backdrop.size
    radius = round(max(width, height) * radius_ratio)
    center_x, center_y = width // 2, round(height * center_ratio)

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).ellipse(
        (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
        fill=opacity,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(radius // 2))
    return Image.composite(Image.new("RGB", (width, height), color), backdrop, mask)


def _palette(image: Image.Image, palette_size: int) -> list[tuple[int, tuple[int, int, int]]]:
    """Return the image's quantized swatches as (pixel count, colour), most frequent first."""
    sample = image.resize((128, 128), Image.Resampling.LANCZOS)
    quantized = sample.quantize(colors=palette_size, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    return [
        (count, (palette[index * 3], palette[index * 3 + 1], palette[index * 3 + 2]))
        for count, index in sorted(quantized.getcolors() or [], reverse=True)
    ]


def _corner_colors(image: Image.Image) -> list[tuple[int, int, int]]:
    """Return four dominant colours of the image, most frequent first."""
    palette_size = 8
    min_saturation = 0.25

    colors = [color for _, color in _palette(image, palette_size)]
    # Greys make a flat, muddy gradient, so prefer the saturated swatches when there are any.
    vivid = [color for color in colors if _saturation(color) >= min_saturation] or colors
    return [vivid[index % len(vivid)] for index in range(4)]


def _vibrance_ranking(image: Image.Image) -> list[tuple[float, tuple[int, int, int]]]:
    """Return the image's swatches scored for vibrance, best first.

    Mirrors Android's Palette vibrant target: how saturated a swatch is and how close it
    sits to mid lightness outweigh how much of the artwork it actually covers, which is
    why a small neon logo beats the large dark photo behind it.
    """
    palette_size = 16
    saturation_weight, lightness_weight, population_weight = 0.24, 0.52, 0.24
    target_saturation, target_lightness = 1.0, 0.5
    lightness_bounds = (0.06, 0.94)

    swatches = _palette(image, palette_size)
    max_population = max((count for count, _ in swatches), default=1)

    ranking = []
    for count, color in swatches:
        _, lightness, saturation = _hls(color)
        if not lightness_bounds[0] < lightness < lightness_bounds[1]:
            continue
        ranking.append(
            (
                (1 - abs(saturation - target_saturation)) * saturation_weight
                + (1 - abs(lightness - target_lightness)) * lightness_weight
                + (count / max_population) * population_weight,
                color,
            )
        )
    return sorted(ranking, key=lambda entry: entry[0], reverse=True)


def _accent_pair(
    image: Image.Image,
) -> tuple[tuple[int, int, int], tuple[int, int, int] | None]:
    """Return the image's accent colour and a second one of a clearly different hue, if any.

    Only artwork that genuinely holds two colours gets a second accent. A pale wash of
    teal beside hot pink still counts, so the bar is low, but it has to be light: a dark
    photo's near-black shadows must not pass as a colour of their own.
    """
    min_saturation = 0.28
    min_lightness = 0.25
    min_hue_distance = 0.12

    ranking = _vibrance_ranking(image)
    if not ranking:
        return _corner_colors(image)[0], None

    primary = ranking[0][1]
    primary_hue = _hls(primary)[0]

    def qualifies(color: tuple[int, int, int]) -> bool:
        hue, lightness, saturation = _hls(color)
        return (
            saturation >= min_saturation
            and lightness >= min_lightness
            and _hue_distance(hue, primary_hue) >= min_hue_distance
        )

    secondary = next((color for _, color in ranking[1:] if qualifies(color)), None)
    return primary, secondary


def gradient_backdrop(image: Image.Image, width: int, height: int) -> Image.Image:
    """Return a full-panel gradient interpolated between the image's dominant colours.

    Plex-style: a handful of dominant swatches placed at the panel corners and
    interpolated into one another by upscaling a 2x2 image.
    """
    brightness = 0.85
    top_left, bottom_right, top_right, bottom_left = _corner_colors(image)

    corners = Image.new("RGB", (2, 2))
    corners.putpixel((0, 0), top_left)
    corners.putpixel((1, 0), top_right)
    corners.putpixel((0, 1), bottom_left)
    corners.putpixel((1, 1), bottom_right)

    backdrop = corners.resize((width, height), Image.Resampling.BICUBIC)
    return ImageEnhance.Brightness(backdrop).enhance(brightness)


def vibrant_backdrop(image: Image.Image, width: int, height: int) -> Image.Image:
    """Return a backdrop painted from the artwork's most vibrant colours.

    """
    paired_brightness = (0.95, 0.75)
    single_brightness = (0.75, 0.95)
    glow_brightness = 1.0
    glow_opacity = 90
    glow_center_ratio = 0.74
    glow_radius_ratio = 0.5
    saturation = 0.95

    primary, secondary = _accent_pair(image)
    other = secondary or primary
    top, bottom = paired_brightness if secondary else single_brightness

    corners = Image.new("RGB", (2, 2))
    corners.putpixel((0, 0), _shade(primary, top))
    corners.putpixel((1, 0), _shade(other, top))
    corners.putpixel((0, 1), _shade(other, bottom))
    corners.putpixel((1, 1), _shade(primary, bottom))
    backdrop = corners.resize((width, height), Image.Resampling.BICUBIC)

    backdrop = _glow_over(
        backdrop,
        _shade(_blend(primary, other), glow_brightness),
        glow_opacity,
        glow_center_ratio,
        glow_radius_ratio,
    )
    return ImageEnhance.Color(backdrop).enhance(saturation)


def blurred_backdrop(image: Image.Image, width: int, height: int) -> Image.Image:
    """Return a full-panel, blurred and muted version of the image."""
    # The radius scales with the panel so the backdrop reads as a wash of colour, not as content.
    blur_ratio = 0.03
    saturation = 0.7
    brightness = 0.8

    backdrop = ImageOps.fit(image, (width, height), Image.Resampling.LANCZOS)
    backdrop = backdrop.filter(
        ImageFilter.GaussianBlur(max(1, round(max(width, height) * blur_ratio)))
    )
    backdrop = ImageEnhance.Color(backdrop).enhance(saturation)
    return ImageEnhance.Brightness(backdrop).enhance(brightness)


def color_wash_backdrop(image: Image.Image, width: int, height: int) -> Image.Image:
    """Return a full-panel wash of the image's colours, vivid and darkened.

    The art is crushed to a few pixels and blown back up, which yields a smooth colour wash
    no Gaussian radius can match, then blurred lightly to kill residual banding.
    """
    wash_width = 24
    blur_ratio = 0.015
    saturation = 1.3
    brightness = 0.65

    wash_height = max(1, round(wash_width * height / width))
    backdrop = ImageOps.fit(image, (wash_width, wash_height), Image.Resampling.LANCZOS)
    backdrop = backdrop.resize((width, height), Image.Resampling.BICUBIC)
    backdrop = backdrop.filter(
        ImageFilter.GaussianBlur(max(1, round(max(width, height) * blur_ratio)))
    )
    backdrop = ImageEnhance.Color(backdrop).enhance(saturation)
    return ImageEnhance.Brightness(backdrop).enhance(brightness)


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    """Return an antialiased mask with the given rounded-rectangle shape."""
    # Drawn oversized and shrunk back, because Pillow's shapes are not antialiased.
    scale = 4

    width, height = size
    mask = Image.new("L", (width * scale, height * scale), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, width * scale - 1, height * scale - 1), radius=radius * scale, fill=255
    )
    return mask.resize(size, Image.Resampling.LANCZOS)


def drop_shadow(
    backdrop: Image.Image, box: tuple[int, int, int, int], radius: int = 0
) -> Image.Image:
    """Darken the backdrop with a soft shadow cast by the given foreground box."""
    blur_ratio = 0.02
    offset_ratio = 0.012
    strength = 210

    width, height = backdrop.size
    left, top, right, bottom = box
    offset = round(max(width, height) * offset_ratio)

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (left, top + offset, right, bottom + offset), radius=radius, fill=strength
    )
    mask = mask.filter(
        ImageFilter.GaussianBlur(max(1, round(max(width, height) * blur_ratio)))
    )
    return Image.composite(Image.new("RGB", (width, height), "black"), backdrop, mask)


def center_on(image: Image.Image, backdrop: Image.Image) -> Image.Image:
    """Return the backdrop with the image scaled to fit and pasted at its centre."""
    width, height = backdrop.size
    foreground = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
    backdrop.paste(
        foreground,
        ((width - foreground.width) // 2, (height - foreground.height) // 2),
    )
    return backdrop


def popout_on(
    image: Image.Image,
    backdrop: Image.Image,
    rounded: bool = True,
) -> Image.Image:
    """Return the backdrop with the image floating over it, margined and shadowed."""
    width, height = backdrop.size
    margin = round(min(width, height) * FOREGROUND_MARGIN_RATIO)
    foreground = ImageOps.contain(
        image, (width - 2 * margin, height - 2 * margin), Image.Resampling.LANCZOS
    )
    left = (width - foreground.width) // 2
    top = (height - foreground.height) // 2
    radius = round(min(foreground.size) * CORNER_RADIUS_RATIO) if rounded else 0

    backdrop = drop_shadow(
        backdrop, (left, top, left + foreground.width, top + foreground.height), radius
    )
    backdrop.paste(
        foreground, (left, top), rounded_mask(foreground.size, radius) if rounded else None
    )
    return backdrop
