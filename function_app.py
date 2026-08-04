import json
import logging

import azure.functions as func

from webhook_helpers import handlers, request

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# https://support.plex.tv/hc/en-us/articles/115002267687-Webhooks
# As stated above, the payload is sent in JSON format inside a multipart
# HTTP POST request. For the media.play and media.rate events.
# A second part of the POST request contains a very small JPEG thumbnail,
# but it is too small to be used in our scenario.

@app.route(route="plex_webhook_trigger", methods=["POST"])
async def http_plex_webhook_trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Received Plex webhook request.")

    try:
        payload = json.loads(req.form["payload"])
    except (KeyError, ValueError):
        logging.warning("Webhook did not contain a valid 'payload' form field.")
        return func.HttpResponse(
            "Invalid webhook payload. Expected Plex 'payload' form field.",
            status_code=400,
        )    

    message, status_code = await handlers.handle_plex_payload(payload)
    return func.HttpResponse(message, status_code=status_code)


@app.route(route="http_restore_trigger", methods=["POST"])
async def http_restore_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """Restore the frame state saved before the last temporary display.

    Query parameters:
        overwrite_state: Optional boolean. When true, restore even if the frame is
            currently showing an image this workflow did not put there.

    Responses:
        200: Restore completed, was skipped, or was cancelled by a newer action.
        500: Restore failed.
    """
    # Forces the restore even when the frame shows an image the workflow did not put there.
    overwrite_state = request.param_flag(req.params, "overwrite_state")
    message, status_code = await handlers.handle_restore(overwrite_state)
    return func.HttpResponse(message, status_code=status_code)


@app.route(route="http_show_image_trigger", methods=["POST"])
async def http_show_image_trigger(req: func.HttpRequest) -> func.HttpResponse:
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
    image_data, uploaded_filename = request.extract_uploaded_image(req)
    image_name = request.resolve_image_name(req.params, uploaded_filename)
    overwrite_state = request.param_flag(req.params, "overwrite_state")
    message, status_code = await handlers.handle_show_image(
        image_data,
        image_name,
        req.params.get("gallery"),
        req.params.get("display_mode"),
        overwrite_state,
    )
    return func.HttpResponse(message, status_code=status_code)

