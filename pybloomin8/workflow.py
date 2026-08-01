"""High-level temporary-image workflow."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from .api import Bloomin8Api
from .ble import wake_device
from .constants import STATE_READY_DELAY_SECONDS
from .image import prepare_image
from .state import DisplayStateStore, is_managed_image

log = logging.getLogger(__name__)


class TemporaryImageWorkflow:
    """Display an image while keeping the ability to restore the previous frame state."""

    def __init__(self, mac_address: str, ip_address: str) -> None:
        self.mac_address = mac_address
        self.api = Bloomin8Api(ip_address)
        self.state_backup = DisplayStateStore(mac_address)

    async def __aenter__(self) -> "TemporaryImageWorkflow":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.api.close()

    async def wake_and_connect(self) -> None:
        """Wake the frame over BLE and allow Wi-Fi startup to begin."""
        await wake_device(self.mac_address)
        try:
            await self.api.wait_until_ready()
        except RuntimeError:
            log.warning("Device did not respond after first BLE wake — retrying wake signal")
            await wake_device(self.mac_address)
            await self.api.wait_until_ready()

    async def replace_image(
        self,
        image_path: Path,
        gallery: str,
        overwrite_state: bool = False,
        dither: int | None = None,
    ) -> None:
        """Save the current state and display a temporary image."""
        log.info("=== Upload temporary image ===")
        await self.wake_and_connect()
        current_state = await self.api.get_device_info()
        self.state_backup.backup_current_state(current_state, overwrite_state)

        log.info("  Current image : %s", current_state.get("image"))
        log.info("  Current gallery : %s", current_state.get("gallery"))
        log.info("  Play mode     : %s", current_state.get("play_type"))


        filename = image_path.name
        if await self.api.image_exists(filename, gallery):
            await self.api.show_image(filename, gallery, dither=dither)
            return

        jpeg_data = prepare_image(image_path, int(current_state["width"]), int(current_state["height"]), fit_mode=fit_mode)
        await self.api.upload_and_show(jpeg_data, filename, gallery, dither=dither)

    async def restore(self, overwrite_state: bool = False) -> None:
        """Restore the previously saved display state and remove temporary data."""
        log.info("=== Restore previous state ===")
        await self.wake_and_connect()
        current_state = await self.api.get_device_info()
        if not is_managed_image(current_state) and not overwrite_state :
            raise RuntimeError(
                "Current display is outside managed galleries. "
                "Refusing to restore over it. Use --overwrite-state to force."
            )

        saved_state = self.state_backup.load()
        await self.api.restore_display(saved_state)
        self.state_backup.delete()
        log.info("=== Previous display restored ===")