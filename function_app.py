import azure.functions as func
import asyncio
import logging
import json
import os
from urllib.parse import quote

import httpx
import pybloomin8

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


def _env_flag(name: str, default: str = "true") -> bool:
    return (os.getenv(name) or default).strip().lower() in ("true", "1", "yes")


PLEX_SERVER_URL = os.getenv("PLEX_SERVER_URL","").strip().rstrip("/")
PLEX_TOKEN = os.getenv("PLEX_TOKEN","")
REQUIRE_OWNER_PLAYBACK = _env_flag("PROCESS_OWNER_PLAYBACK_ONLY","true")
REQUIRE_LOCAL_PLAYER = _env_flag("PROCESS_LOCAL_PLAYBACK_ONLY","true")
STOP_DEBOUNCE_SECONDS = int(os.getenv("STOP_DEBOUNCE_SECONDS", "25"))
POSTER_DOWNLOAD_TIMEOUT_SECONDS = 20.0
POSTER_MAX_BYTES = 16 * 1024 * 1024
BLOOMIN8_SHOW_POSTER_GALLERY = "shows"

# TODO : Resolve once at load so an invalid frame configuration fails at startup, not mid-webhook.
# pybloomin8.get_settings()

# The debounced restore is held in a module global so it survives the webhook response.
_pending_restore: asyncio.Task | None = None


def cancel_pending_restore() -> None:
    global _pending_restore

    # cancel() returns False when the restore already ran, so this only logs real cancellations.
    if _pending_restore is not None and _pending_restore.cancel():
        logging.info("Pending restore cancelled by a newer event.")

    _pending_restore = None


def schedule_stop() -> asyncio.Task:
    """Restore the frame after the debounce window, unless a play arrives first."""
    global _pending_restore

    cancel_pending_restore()
    _pending_restore = asyncio.create_task(_restore_later())
    return _pending_restore


async def perform_restore(overwrite_state: bool = False) -> None:
    logging.info("Restoring frame state (overwrite_state=%s).", overwrite_state)
    await pybloomin8.restore(overwrite_state=overwrite_state)
    logging.info("Restore completed.")


async def _restore_later() -> None:
    global _pending_restore

    await asyncio.sleep(STOP_DEBOUNCE_SECONDS)
    # Past the window the restore is committed; a later play must not interrupt it.
    _pending_restore = None

    logging.info("Media stop confirmed : debounce delay elapsed")
    try:
        await perform_restore()
    except Exception:
        logging.exception("Restore failed.")


async def download_poster(poster_url: str) -> bytes:
    """Fetch the poster into memory, refusing responses larger than POSTER_MAX_BYTES."""
    async with httpx.AsyncClient(timeout=POSTER_DOWNLOAD_TIMEOUT_SECONDS) as client:
        async with client.stream("GET", poster_url) as response:
            response.raise_for_status()

            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks += chunk
                if len(chunks) > POSTER_MAX_BYTES:
                    raise ValueError(f"Poster exceeds {POSTER_MAX_BYTES} bytes.")

    return bytes(chunks)


async def temp_show_poster(poster_url: str, poster_id: str) -> None:
    logging.info("Displaying poster %s: %s", poster_id, poster_url)
    try:
        poster_data = await download_poster(poster_url)
        await pybloomin8.temp_show_image_from_bytes(poster_data, poster_id, gallery=BLOOMIN8_SHOW_POSTER_GALLERY)
        logging.info("Display completed.")
    except Exception:
        # A frame failure is not the sender's problem, so it is logged rather than raised.
        logging.exception("Display failed.")


def should_skip_webhook(payload: dict) -> bool:
    # Each restriction is opt-in via its own env var, defaulting to enabled.
    if REQUIRE_OWNER_PLAYBACK and not payload.get("owner"):
        logging.info("Skipping webhook: owner-only playback restriction not met.")
        return True

    if REQUIRE_LOCAL_PLAYER and not (payload.get("Player") or {}).get("local"):
        logging.info("Skipping webhook: local-player restriction not met.")
        return True

    # Only media.play and media.stop are relevant for our workflow; ignore the rest.
    if payload.get("event") not in ("media.play", "media.stop"):
        logging.info("Skipping webhook: event '%s' is not media.play/media.stop.", payload.get("event"))
        return True

    return False


def build_thumb_url(library_partial_path: str | None) -> str | None:
    # Resolves a Plex-relative thumb path (e.g. "/library/metadata/123/thumb/456")
    # into a fully qualified URL against PLEX_SERVER_URL, authenticated with PLEX_TOKEN.
    if not library_partial_path or not PLEX_SERVER_URL:
        return None

    url = f"{PLEX_SERVER_URL}{library_partial_path}"
    if not PLEX_TOKEN:
        return url

    # Metadata paths from Plex never carry a query string of their own, so we can always append token once escaped.
    return f"{url}?X-Plex-Token={quote(PLEX_TOKEN, safe='')}"

def extract_movie_poster(metadata):
    poster_plex_partial_path = metadata.get("thumb")
    poster_item_id = metadata.get("ratingKey")
    logging.info("Getting movie poster: poster_item_id=%s", poster_item_id)
    return poster_plex_partial_path,poster_item_id

def extract_show_poster(metadata):
    if metadata.get("parentThumb"):
        poster_plex_partial_path = metadata.get("parentThumb")
        poster_item_id = metadata.get("parentRatingKey")
        logging.info(
                "Getting season poster : grandparentTitle=%s, parentTitle=%s",
                metadata.get("grandparentTitle"),
                metadata.get("parentTitle"),
            )
    else:
        poster_plex_partial_path = metadata.get("grandparentThumb")
        poster_item_id = metadata.get("grandparentRatingKey")
        logging.info(
                "Getting show poster: grandparentTitle=%s",
                metadata.get("grandparentTitle"),
            )
    return poster_plex_partial_path,poster_item_id


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

    if should_skip_webhook(payload):
        return func.HttpResponse("OK", status_code=200)

    event_name = payload.get("event")
    logging.info("Plex webhook event: %s", event_name)

    if event_name == "media.stop":
        restore_task = schedule_stop()
        logging.info("Holding the response for up to %ss before restoring.", STOP_DEBOUNCE_SECONDS)

        # Waiting inside the invocation stops the host from tearing the worker down mid-debounce.
        # asyncio.wait() returns instead of raising when a newer event cancels the task.
        await asyncio.wait({restore_task})

        if restore_task.cancelled():
            return func.HttpResponse("Restore cancelled by a newer event.", status_code=200)

        return func.HttpResponse("Restored", status_code=200)
    else:
        metadata = payload.get("Metadata") or {}
        media_type = metadata.get("type")
        poster_plex_partial_path = poster_item_id = None

        # Episode thumbs are preview frames, not posters; use the season/show art and its rating key instead.
        if media_type == "episode":
            poster_plex_partial_path, poster_item_id = extract_show_poster(metadata)
        elif media_type == "movie":
            poster_plex_partial_path, poster_item_id = extract_movie_poster(metadata)

        poster_full_url = build_thumb_url(poster_plex_partial_path)
        if not poster_full_url or not poster_item_id:
            logging.info("No poster resolved for media type '%s'; frame left unchanged.", media_type)
            return func.HttpResponse("OK", status_code=200)

        logging.info("Poster: name=%s url=%s", poster_item_id, poster_full_url)
        cancel_pending_restore()
        await temp_show_poster(poster_full_url, poster_item_id)
        return func.HttpResponse("OK", status_code=200)


@app.route(route="http_restore_trigger", methods=["POST"])
async def http_restore_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """Restore the saved frame state now, bypassing the stop debounce."""
    # Forces the restore even when the frame shows an image the workflow did not put there.
    overwrite_state = (req.params.get("overwrite_state") or "").strip().lower() in ("true", "1", "yes")
    logging.info("Restore requested over HTTP (overwrite_state=%s).", overwrite_state)

    # A pending debounced restore would otherwise fire later against already-restored state.
    cancel_pending_restore()

    try:
        await perform_restore(overwrite_state)
    except Exception as error:
        logging.exception("Restore failed.")
        return func.HttpResponse(f"Restore failed: {error}", status_code=500)

    return func.HttpResponse("Restored", status_code=200)

