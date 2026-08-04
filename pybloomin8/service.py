"""Environment-configured entry points for embedding pybloomin8 in a service."""

from .image import DisplayMode
from .settings import get_settings
from .workflow import TemporaryImageWorkflow


async def temp_show_image_from_bytes(
    image_data: bytes,
    name: str,
    gallery: str | None = None,
    display_mode: DisplayMode | None = None,
    dither: int | None = None,
    overwrite_state: bool = False,
    only_if_idle: bool | None = None,
) -> bool:
    """Display an in-memory image on the frame configured by the environment.

    With `only_if_idle` (or BLOOMIN8_ONLY_IF_IDLE), nothing is displayed when the
    frame is busy. Returns whether the frame now shows the requested image.
    """
    settings = get_settings()
    async with TemporaryImageWorkflow(
        settings.mac, settings.ip, settings.managed_galleries
    ) as workflow:
        return await workflow.replace_image_bytes(
            image_data,
            gallery or settings.gallery,
            name,
            overwrite_state=overwrite_state,
            dither=dither,
            display_mode=display_mode or settings.display_mode,
            only_if_idle=settings.only_if_idle if only_if_idle is None else only_if_idle,
        )


async def restore(overwrite_state: bool = False) -> None:
    """Restore the frame state saved before the last show."""
    settings = get_settings()
    async with TemporaryImageWorkflow(
        settings.mac, settings.ip, settings.managed_galleries
    ) as workflow:
        await workflow.restore(overwrite_state=overwrite_state)
