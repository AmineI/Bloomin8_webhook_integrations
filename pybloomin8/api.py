"""Async client for the Bloomin8 HTTP API."""

import asyncio
import logging
import time
from types import TracebackType
from typing import Any, Self

import httpx

from pybloomin8.constants import (
    HTTP_REQUEST_TIMEOUT_SECONDS,
    HTTP_UPLOAD_TIMEOUT_SECONDS,
    SHOW_RETRY_ATTEMPTS,
    STATE_READY_DELAY_SECONDS,
    STATE_READY_STATUS_RETURN_CODE,
    STATE_READY_TIMEOUT_SECONDS,
)

log = logging.getLogger(__name__)


def gallery_image_path(gallery: str, filename: str) -> str:
    """Return the device-side path used by both /show and deviceInfo's `image`."""
    return f"/gallerys/{gallery}/{filename}"


class Bloomin8Api:
    """Manage HTTP requests to one Bloomin8 frame."""

    def __init__(self, ip_address: str) -> None:
        self.ip_address = ip_address
        self._client = httpx.AsyncClient(base_url=f"http://{ip_address}")

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        await self._client.aclose()

    async def wait_until_ready(
        self, timeout: float = STATE_READY_TIMEOUT_SECONDS
    ) -> None:
        """Wait until the frame is ready for tasks."""
        log.info("[Bloomin8 API] Waiting for device at %s", self.ip_address)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            try:
                response = await self._client.get("/state", timeout=3.0)
                try:
                    payload = response.json()
                except ValueError:
                    payload = None
                log.info(
                    "[Bloomin8 API] /state -> HTTP %s %s",
                    response.status_code,
                    payload if payload is not None else response.text,
                )
                if (
                    response.status_code == 200
                    and isinstance(payload, dict)
                    and payload.get("status") == STATE_READY_STATUS_RETURN_CODE
                ):
                    log.info("[Bloomin8 API] Device task state is ready")
                    return
            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.RemoteProtocolError,
            ):
                pass
            await asyncio.sleep(STATE_READY_DELAY_SECONDS)

        raise RuntimeError(
            f"Device at {self.ip_address} did not become ready within {timeout}s"
        )

    async def _post_show(
        self, payload: dict[str, Any], attempts: int = SHOW_RETRY_ATTEMPTS
    ) -> None:
        """POST to /show, retrying while the frame reports it is busy (5xx)."""
        for attempt in range(1, attempts + 1):
            response = await self._client.post(
                "/show",
                json=payload,
                timeout=HTTP_REQUEST_TIMEOUT_SECONDS,
            )
            if response.is_server_error and attempt < attempts:
                log.warning(
                    "[Bloomin8 API] /show returned %s (attempt %d/%d), retrying in %ss",
                    response.status_code,
                    attempt,
                    attempts,
                    STATE_READY_DELAY_SECONDS,
                )
                await asyncio.sleep(STATE_READY_DELAY_SECONDS)
                continue
            response.raise_for_status()
            return

    async def get_device_info(self) -> dict[str, Any]:
        """Return the frame's current display state and dimensions."""
        response = await self._client.get("/deviceInfo", timeout=HTTP_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()

    async def image_exists(self, filename: str, gallery: str) -> bool:
        """Return whether a named image already exists in a gallery."""
        cursor: str | None = None

        while True:
            params: dict[str, str | int] = {
                "gallery_name": gallery,
                "offset": 0,
                "limit": 50,
                "full": 1,
            }
            if cursor:
                params["cursor"] = cursor

            response = await self._client.get("/gallery", params=params, timeout=HTTP_REQUEST_TIMEOUT_SECONDS)
            if not response.is_success:
                return False

            result = response.json()
            if any(image.get("name") == filename for image in result.get("data", [])):
                return True

            cursor = result.get("cursor_next")
            if not result.get("more") or not cursor:
                return False

    async def show_image(
        self, filename: str, gallery: str, dither: int | None = None
    ) -> None:
        """Display an image that is already stored on the frame."""
        payload: dict[str, Any] = {
            "play_type": 0,
            "image": gallery_image_path(gallery, filename),
        }
        if dither is not None:
            payload["dither"] = dither

        await self.wait_until_ready()
        await self._post_show(payload)
        log.info("[Bloomin8 API] Existing image displayed: %s/%s", gallery, filename)

    async def upload_and_show(
        self,
        jpeg_data: bytes,
        filename: str,
        gallery: str,
        dither: int | None = None,
    ) -> None:
        """Persist a named JPEG and display it immediately."""
        params: dict[str, str | int] = {
            "filename": filename,
            "gallery": gallery,
            "show_now": 1,
        }
        if dither is not None:
            params["dither"] = dither
        await self.wait_until_ready()
        response = await self._client.post(
            "/upload",
            params=params,
            files={"image": (filename, jpeg_data, "image/jpeg")},
            timeout=HTTP_UPLOAD_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        log.info("[Bloomin8 API] Image persisted and displayed: %s/%s", gallery, filename)

    async def restore_display(self, saved_state: dict[str, Any]) -> None:
        """Restore a display state previously returned by deviceInfo."""
        play_type = int(saved_state.get("play_type", 0))
        payload: dict[str, Any] = {
            "image": saved_state["image"],
            "play_type": saved_state["play_type"],
            "dither": saved_state["dither"],
            "saturation": saved_state["saturation"],
            "gamma": saved_state["gamma"],
            "gallery": saved_state.get("gallery", "default"),
        }

        if play_type == 1:
            payload["duration"] = saved_state.get("play_duration", 300)
        elif play_type == 2:
            payload["playlist"] = saved_state.get("playlist", "")
        await self.wait_until_ready()
        await self._post_show(payload)

        log.info("[Bloomin8 API] Restored backed up display status")

    async def delete_gallery(self, name: str) -> None:
        """Delete an entire gallery and all images contained within it."""
        response = await self._client.delete(
            "/gallery",
            params={"name": name},
            timeout=HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        log.info("[Bloomin8 API] Gallery '%s' deleted", name)

    async def sleep(self) -> None:
        """Put the frame into sleep mode."""
        await self.wait_until_ready()
        response = await self._client.post("/sleep", timeout=HTTP_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        log.info("[Bloomin8 API] Frame sent to sleep")
