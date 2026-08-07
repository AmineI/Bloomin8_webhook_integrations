"""Framework-neutral webhook handlers shared by Azure Functions and Starlette."""

import asyncio
import logging
import time

import pybloomin8
from pybloomin8 import settings
from pybloomin8.ble import wake_device
from pybloomin8.image import DisplayMode

from . import config, debounce, plex

_last_wake_started_at: float | None = None


async def _ble_prewake() -> None:
    global _last_wake_started_at

    now = time.monotonic()
    if _last_wake_started_at is not None and now - _last_wake_started_at < config.WEBHOOK_BLE_WAKE_DEBOUNCE_SECONDS:
        logging.info("Skipping pre-debounce BLE wake: already started within %ss.", config.WEBHOOK_BLE_WAKE_DEBOUNCE_SECONDS)
        return

    _last_wake_started_at = now
    frame_settings = pybloomin8.get_settings()
    await wake_device(frame_settings.mac)


async def show_plex_poster(poster_url: str, poster_filename: str, display_mode: DisplayMode, gallery: str) -> bool:
    """Download the poster from Plex and display it, unless the frame is busy."""
    logging.info("Downloading poster %s: %s", poster_filename, poster_url.split("?")[0])
    poster_data = await plex.download_poster(poster_url)
    return await pybloomin8.temp_show_image_from_bytes(
        poster_data,
        poster_filename,
        gallery=gallery,
        display_mode=display_mode,
        overwrite_state=config.WEBHOOK_DEFAULT_OVERWRITE_STATE,
        only_if_idle=config.WEBHOOK_ACTION_ONLY_IF_IDLE,
    )


async def handle_plex_payload(payload: dict) -> tuple[str, int]:
    if plex.should_skip_webhook(payload):
        return "OK", 200

    event_name = payload.get("event")
    logging.info("Plex webhook event: %s", event_name)

    if event_name == "media.stop":
        restore_task = debounce.schedule(
            lambda: pybloomin8.restore(config.WEBHOOK_DEFAULT_OVERWRITE_STATE, skip_wake=True),
            config.WEBHOOK_RESTORE_DEBOUNCE_SECONDS,
            during_delay=_ble_prewake,
        )
        return await debounce.wait_for_result(restore_task, "Restore")
    else:
        metadata = payload.get("Metadata") or {}
        try:
            poster_plex_partial_path, poster_filename = plex.extract_media_poster(metadata)
        except LookupError as error:
            logging.warning("%s; frame left unchanged.", error)
            return str(error), 404

    
        if metadata.get("type") == "track":
            poster_display_mode: DisplayMode = config.TRACK_DISPLAY_MODE
            gallery = config.BLOOMIN8_MUSIC_ART_GALLERY
        else:
            poster_display_mode = "cover"
            gallery = config.BLOOMIN8_MEDIA_POSTER_GALLERY

        poster_full_url = plex.build_thumb_url(poster_plex_partial_path)
        if not poster_full_url:
            logging.warning("WEBHOOK_PLEX_SERVER_URL is not configured; frame left unchanged.")
            return "WEBHOOK_PLEX_SERVER_URL is not configured.", 500

        show_task = debounce.schedule(
            lambda: show_plex_poster(poster_full_url, poster_filename, poster_display_mode, gallery),
            config.WEBHOOK_SHOW_DEBOUNCE_SECONDS,
        )
        return await debounce.wait_for_result(show_task, "Display")


async def handle_restore(overwrite_state: bool) -> tuple[str, int]:
    logging.info("Restore requested over HTTP (overwrite_state=%s).", overwrite_state)

    restore_task = debounce.schedule(
        lambda: pybloomin8.restore(overwrite_state, skip_wake=True),
        config.WEBHOOK_RESTORE_DEBOUNCE_SECONDS,
        during_delay=_ble_prewake,
    )
    return await debounce.wait_for_result(restore_task, "Restore")


async def handle_show_image(
    image_data: bytes,
    image_name: str | None,
    gallery_name: str | None,
    display_mode_name: str | None,
    overwrite_state: bool,
) -> tuple[str, int]:
    if not image_data:
        return "No image supplied.", 400

    if len(image_data) > config.POSTER_MAX_BYTES:
        return f"Image exceeds {config.POSTER_MAX_BYTES} bytes.", 400

    if image_name is None:
        return "Missing 'name'. Supply it as a query parameter or as the upload filename.", 400

    frame_settings = pybloomin8.get_settings()

    try:
        gallery = settings.resolve_gallery(gallery_name, frame_settings.managed_galleries)
        display_mode = settings.resolve_display_mode(display_mode_name)
    except ValueError as error:
        return str(error), 400

    show_task = debounce.schedule(
        lambda: pybloomin8.temp_show_image_from_bytes(
            image_data,
            image_name,
            gallery=gallery,
            display_mode=display_mode,
            overwrite_state=overwrite_state,
        ),
        config.WEBHOOK_SHOW_DEBOUNCE_SECONDS,
    )
    return await debounce.wait_for_result(show_task, "Display")