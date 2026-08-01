import azure.functions as func
import logging
import json
import os
from urllib.parse import quote

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


def _env_flag(name: str, default: str = "true") -> bool:
    return (os.getenv(name) or default).strip().lower() in ("true", "1", "yes")


PLEX_SERVER_URL = os.getenv("PLEX_SERVER_URL","").strip().rstrip("/")
PLEX_TOKEN = os.getenv("PLEX_TOKEN","")
REQUIRE_OWNER_PLAYBACK = _env_flag("PROCESS_OWNER_PLAYBACK_ONLY","true")
REQUIRE_LOCAL_PLAYER = _env_flag("PROCESS_LOCAL_PLAYBACK_ONLY","true")

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

@app.route(route="http_webhook_trigger")
def http_webhook_trigger(req: func.HttpRequest) -> func.HttpResponse:
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
        logging.info("Media stopped. No further processing required.")
        # TODO RESTORE The image to the last known good state, if any
        return func.HttpResponse("OK", status_code=200)
    else:
        logging.info("Media started. Sending image.")
    
        metadata = payload.get("Metadata") or {}
        media_type = metadata.get("type")

        # Episode thumbs are preview frames, not posters; use the season/show art and its rating key instead.
        if media_type == "episode":
            poster_plex_partial_path, poster_item_id = extract_show_poster(metadata)
        elif media_type == "movie":
            poster_plex_partial_path, poster_item_id = extract_movie_poster(metadata)

        poster_full_url = build_thumb_url(poster_plex_partial_path)

        logging.info("Poster: name=%s url=%s", poster_item_id, poster_full_url)
        #TODO Get the image from poster_full_url & send to the Bloomin8 device to update the image

    return func.HttpResponse("OK", status_code=200)

