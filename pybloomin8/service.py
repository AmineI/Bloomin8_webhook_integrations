"""Environment-configured entry points for embedding pybloomin8 in a service."""

from .image import FitMode
from .settings import get_settings
from .workflow import TemporaryImageWorkflow


async def temp_show_image_from_bytes(
    image_data: bytes,
    name: str,
    gallery: str | None = None,
    fit_mode: FitMode | None = None,
    dither: int | None = None,
    overwrite_state: bool = False,
) -> None:
    """Display an in-memory image on the frame configured by the environment."""
    settings = get_settings()
    async with TemporaryImageWorkflow(
        settings.mac, settings.ip, settings.managed_galleries
    ) as workflow:
        await workflow.replace_image_bytes(
            image_data,
            gallery or settings.gallery,
            name,
            overwrite_state=overwrite_state,
            dither=dither,
            fit_mode=fit_mode or settings.fit_mode,
        )


async def restore(overwrite_state: bool = False) -> None:
    """Restore the frame state saved before the last show."""
    settings = get_settings()
    async with TemporaryImageWorkflow(
        settings.mac, settings.ip, settings.managed_galleries
    ) as workflow:
        await workflow.restore(overwrite_state=overwrite_state)
