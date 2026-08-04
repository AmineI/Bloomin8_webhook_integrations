"""Plain Python webhook server for Bloomin8.

Run with:
    uvicorn webhook_server:app --host 0.0.0.0 --port 7072
"""

import json
import logging
import os

from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from webhook_helpers import handlers, request as webhook_request

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)


async def _extract_uploaded_image(request: Request) -> tuple[bytes, str | None]:
    content_type = (request.headers.get("Content-Type") or "").lower()

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        uploaded = form.get("image")
        if not isinstance(uploaded, UploadFile):
            return b"", None
        return await uploaded.read(), uploaded.filename

    return await request.body(), None


async def plex_webhook_trigger(request: Request) -> PlainTextResponse:
    logging.info("Received Plex webhook request.")

    try:
        form = await request.form()
        payload = json.loads(form["payload"])
    except (KeyError, ValueError, TypeError):
        logging.warning("Webhook did not contain a valid 'payload' form field.")
        return PlainTextResponse(
            "Invalid webhook payload. Expected Plex 'payload' form field.",
            status_code=400,
        )

    message, status_code = await handlers.handle_plex_payload(payload)
    return PlainTextResponse(message, status_code=status_code)


async def restore_trigger(request: Request) -> PlainTextResponse:
    """Restore the frame state saved before the last temporary display.

    Query parameters:
        overwrite_state: Optional boolean. When true, restore even if the frame is
            currently showing an image this workflow did not put there.

    Responses:
        200: Restore completed, was skipped, or was cancelled by a newer action.
        500: Restore failed.
    """
    overwrite_state = webhook_request.param_flag(request.query_params, "overwrite_state")
    message, status_code = await handlers.handle_restore(overwrite_state)
    return PlainTextResponse(message, status_code=status_code)


async def show_image_trigger(request: Request) -> PlainTextResponse:
    """Display an uploaded image temporarily on the frame.

    Accepts either raw image bytes as the request body or multipart/form-data with an
    image field named ``image``. The image name comes from the ``name`` query parameter
    or, for multipart uploads, from the uploaded filename.

    Query parameters:
        name: Optional filename to use on the frame. Required for raw-body uploads.
        gallery: Optional destination gallery. Defaults to the configured gallery.
        display_mode: Optional display mode such as cover, fit, pad, or vibrant-popout.
        overwrite_state: Optional boolean. When true, replace any existing saved state.

    Responses:
        200: Image display completed, was skipped, or was cancelled by a newer action.
        400: Missing image, missing name, oversized image, or invalid gallery/display mode.
        500: Display failed.
    """
    image_data, uploaded_filename = await _extract_uploaded_image(request)
    image_name = webhook_request.resolve_image_name(request.query_params, uploaded_filename)
    overwrite_state = webhook_request.param_flag(request.query_params, "overwrite_state")
    message, status_code = await handlers.handle_show_image(
        image_data,
        image_name,
        request.query_params.get("gallery"),
        request.query_params.get("display_mode"),
        overwrite_state,
    )
    return PlainTextResponse(message, status_code=status_code)


async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK", status_code=200)


app = Starlette(
    routes=[
        Route("/api/plex_webhook_trigger", plex_webhook_trigger, methods=["POST"]),
        Route("/api/http_restore_trigger", restore_trigger, methods=["POST"]),
        Route("/api/http_show_image_trigger", show_image_trigger, methods=["POST"]),
        Route("/webhook", plex_webhook_trigger, methods=["POST"]),
        Route("/restore", restore_trigger, methods=["POST"]),
        Route("/show-image", show_image_trigger, methods=["POST"]),
        Route("/health", health, methods=["GET"]),
    ]
)