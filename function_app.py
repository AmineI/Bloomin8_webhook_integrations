import json
import logging

import azure.functions as func

import pybloomin8
from pybloomin8.image import DisplayMode
from pybloomin8 import settings

from webhook_helpers import config, debounce, plex, request

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


async def show_plex_poster(poster_url: str, poster_filename: str, display_mode: DisplayMode) -> bool:
    """Download the poster from Plex and display it, unless the frame is busy."""
    logging.info("Downloading poster %s: %s", poster_filename, poster_url)
    poster_data = await plex.download_poster(poster_url)
    return await pybloomin8.temp_show_image_from_bytes(
        poster_data,
        poster_filename,
        gallery=config.BLOOMIN8_MEDIA_POSTER_GALLERY,
        display_mode=display_mode,
        overwrite_state=config.PLEX_OVERWRITE_STATE,
        only_if_idle=config.PLEX_ACTION_ONLY_IF_IDLE,
    )


# https://support.plex.tv/hc/en-us/articles/115002267687-Webhooks
# As stated above, the payload is sent in JSON format inside a multipart
# HTTP POST request. For the media.play and media.rate events.
# A second part of the POST request contains a very small JPEG thumbnail,
# but it is too small to be used in our scenario.

@app.route(route="plex_webhook_trigger", methods=["POST"])
async def http_webhook_trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Received Plex webhook request.")

    try:
        payload = json.loads(req.form["payload"])
    except (KeyError, ValueError):
        logging.warning("Webhook did not contain a valid 'payload' form field.")
        return func.HttpResponse(
            "Invalid webhook payload. Expected Plex 'payload' form field.",
            status_code=400,
        )    

    if plex.should_skip_webhook(payload):
        return func.HttpResponse("OK", status_code=200)

    event_name = payload.get("event")
    logging.info("Plex webhook event: %s", event_name)

    if event_name == "media.stop":
        restore_task = debounce.schedule(
            lambda: pybloomin8.restore(config.PLEX_OVERWRITE_STATE), config.RESTORE_DEBOUNCE_SECONDS
        )
        message, status_code = await debounce.wait_for_result(restore_task, "Restore")
        return func.HttpResponse(message, status_code=status_code)
    else:
        metadata = payload.get("Metadata") or {}
        try:
            poster_plex_partial_path, poster_filename = plex.extract_media_poster(metadata)
        except LookupError as error:
            logging.warning("%s; frame left unchanged.", error)
            return func.HttpResponse(str(error), status_code=404)

        # Album art is square, so it gets the backdrop treatment; posters already fill the frame.
        poster_display_mode: DisplayMode = config.TRACK_DISPLAY_MODE if metadata.get("type") == "track" else "cover"

        poster_full_url = plex.build_thumb_url(poster_plex_partial_path)
        if not poster_full_url:
            logging.warning("PLEX_SERVER_URL is not configured; frame left unchanged.")
            return func.HttpResponse("PLEX_SERVER_URL is not configured.", status_code=500)

        show_task = debounce.schedule(
            lambda: show_plex_poster(poster_full_url, poster_filename, poster_display_mode),
            config.SHOW_DEBOUNCE_SECONDS,
        )
        message, status_code = await debounce.wait_for_result(show_task, "Display")
        return func.HttpResponse(message, status_code=status_code)


@app.route(route="http_restore_trigger", methods=["POST"])
async def http_restore_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """Restore the saved frame state now, bypassing the stop debounce."""
    # Forces the restore even when the frame shows an image the workflow did not put there.
    overwrite_state = request.param_flag(req, "overwrite_state")
    logging.info("Restore requested over HTTP (overwrite_state=%s).", overwrite_state)

    # Scheduling with no delay also drops any pending action that would fire against restored state.
    restore_task = debounce.schedule(lambda: pybloomin8.restore(overwrite_state), config.RESTORE_DEBOUNCE_SECONDS)
    message, status_code = await debounce.wait_for_result(restore_task, "Restore")
    return func.HttpResponse(message, status_code=status_code)


@app.route(route="http_show_image_trigger", methods=["POST"])
async def http_show_image_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """Display an image posted as the raw request body or as a multipart 'image' field."""
    image_data, uploaded_filename = request.extract_uploaded_image(req)
    if not image_data:
        return func.HttpResponse("No image supplied.", status_code=400)

    if len(image_data) > config.POSTER_MAX_BYTES:
        return func.HttpResponse(f"Image exceeds {config.POSTER_MAX_BYTES} bytes.", status_code=400)

    image_name = request.resolve_image_name(req, uploaded_filename)
    if image_name is None:
        return func.HttpResponse(
            "Missing 'name'. Supply it as a query parameter or as the upload filename.",
            status_code=400,
        )

    settings = pybloomin8.get_settings()

    try:
        gallery = settings.resolve_gallery(req.params.get("gallery"), settings.managed_galleries)
        display_mode = settings.resolve_display_mode(req.params.get("display_mode"))
    except ValueError as error:
        return func.HttpResponse(str(error), status_code=400)

    overwrite_state = request.param_flag(req, "overwrite_state")
    show_task = debounce.schedule(
        lambda: pybloomin8.temp_show_image_from_bytes(
            image_data,
            image_name,
            gallery=gallery,
            display_mode=display_mode,
            overwrite_state=overwrite_state,
        ),
        config.SHOW_DEBOUNCE_SECONDS,
    )

    message, status_code = await debounce.wait_for_result(show_task, "Display")
    return func.HttpResponse(message, status_code=status_code)

