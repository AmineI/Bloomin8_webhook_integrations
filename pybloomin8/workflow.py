"""High-level temporary-image workflow."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from .api import Bloomin8Api, gallery_image_path, safe_filename
from .ble import wake_device
from .constants import STATE_READY_DELAY_SECONDS
from .image import DisplayMode, prepare_image
from .state import DisplayStateStore, is_managed_image

log = logging.getLogger(__name__)


class TemporaryImageWorkflow:
    """Display an image while keeping the ability to restore the previous frame state."""

    def __init__(
        self,
        mac_address: str,
        ip_address: str,
        managed_galleries: tuple[str, ...],
    ) -> None:
        self.mac_address = mac_address
        self.api = Bloomin8Api(ip_address)
        self.managed_galleries = managed_galleries
        self.state_backup = DisplayStateStore(mac_address, managed_galleries)

    async def __aenter__(self) -> "TemporaryImageWorkflow":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.api.close()

    async def wake_and_connect(self, abort_when_busy: bool = False) -> None:
        """Wake the frame over BLE and allow Wi-Fi startup to begin."""
        await wake_device(self.mac_address)
        try:
            await self.api.wait_until_ready(abort_when_busy=abort_when_busy)
        except RuntimeError:
            log.warning("Device did not respond after first BLE wake — retrying wake signal")
            await wake_device(self.mac_address)
            await self.api.wait_until_ready(abort_when_busy=abort_when_busy)

    async def replace_image_path(
        self,
        image_path: Path,
        gallery: str,
        overwrite_state: bool = False,
        dither: int | None = None,
        display_mode: DisplayMode = "cover",
        only_if_idle: bool = False,
    ) -> bool:
        """Save the current state and display a temporary image read from disk."""
        return await self.replace_image_bytes(
            image_path.read_bytes(),
            gallery,
            image_path.stem,
            overwrite_state=overwrite_state,
            dither=dither,
            display_mode=display_mode,
            only_if_idle=only_if_idle,
        )

    async def replace_image_bytes(
        self,
        image_data: bytes,
        gallery: str,
        name: str,
        overwrite_state: bool = False,
        dither: int | None = None,
        display_mode: DisplayMode = "cover",
        only_if_idle: bool = False,
    ) -> bool:
        """Save the current state and display a temporary image held in memory.

        `name` identifies the image on the frame, so reusing it skips the re-upload.
        With `only_if_idle`, the frame is left untouched when it reports it is busy
        with another task. Returns whether the frame now shows the requested image.
        """
        log.info("=== Upload temporary image  (overwrite_state=%s) ===", overwrite_state)
        log.info(
            "  Requested     : %s -> %s (display_mode=%s, %d bytes)",
            name,
            gallery,
            display_mode,
            len(image_data),
        )
        try:
            await self.wake_and_connect(abort_when_busy=only_if_idle)
        except BlockingIOError as error:
            log.info("Skipping show: %s", error)
            return False
        current_state = await self.api.get_device_info()

        log.info("  Current image : %s", current_state.get("image"))
        log.info("  Current gallery : %s", current_state.get("gallery"))
        log.info("  Play mode     : %s", current_state.get("play_type"))

        # Only act if the current image is not the same as the target image.
        bloomin8_filename = f"{safe_filename(name)}_{display_mode}.jpg"
        target_bloomin8_path = gallery_image_path(gallery, bloomin8_filename)

        # Only play_type 0 holds a still image; under slideshow modes the match is transient.
        if current_state.get("image") == target_bloomin8_path and int(current_state.get("play_type", 0)) == 0:
            log.info("Skipping refresh: Image was already displayed %s", target_bloomin8_path)
            return True

        self.state_backup.backup_current_state(current_state, overwrite_state)


        if await self.api.image_exists(bloomin8_filename, gallery):
            await self.api.show_image(bloomin8_filename, gallery, dither=dither)
            return True

        prepared_image = prepare_image(image_data, int(current_state["width"]), int(current_state["height"]), display_mode=display_mode)
        await self.api.upload_and_show(prepared_image, bloomin8_filename, gallery, dither=dither)
        return True

    async def restore(self, overwrite_state: bool = False) -> None:
        """Restore the previously saved display state and remove temporary data."""
        log.info("=== Restore previous state (overwrite_state=%s) ===", overwrite_state)
        await self.wake_and_connect()
        current_state = await self.api.get_device_info()
        if not is_managed_image(current_state, self.managed_galleries) and not overwrite_state :
            raise RuntimeError(
                "Current display is outside managed galleries. "
                "Refusing to restore over it. Use --overwrite-state to force."
            )

        saved_state = self.state_backup.load()
        await self.api.restore_display(saved_state)
        self.state_backup.delete()
        log.info("=== Previous display restored ===")