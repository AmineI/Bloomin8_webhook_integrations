"""Plex webhook payload handling: filtering, poster resolution and download."""

import logging
from urllib.parse import quote

import httpx

from .config import (
    WEBHOOK_PLEX_SERVER_URL,
    WEBHOOK_PLEX_TOKEN,
    POSTER_DOWNLOAD_TIMEOUT_SECONDS,
    POSTER_MAX_BYTES,
    REQUIRE_LOCAL_PLAYER,
    REQUIRE_OWNER_PLAYBACK,
    WEBHOOK_PLEX_PROCESS_MEDIA_TYPES,
)

# Filename labels used when falling back to a parent/grandparent item.
ANCESTOR_LABELS = {"episode": ("season", "show"), "track": ("album", "artist")}


def should_skip_webhook(payload: dict) -> bool:
    # Each restriction is opt-in via its own env var, defaulting to enabled.

    if REQUIRE_LOCAL_PLAYER and not (payload.get("Player") or {}).get("local"):
        logging.info("Skipping webhook: local-player restriction not met.")
        return True

    if REQUIRE_OWNER_PLAYBACK and not payload.get("owner"):
        logging.info("Skipping webhook: owner-only playback restriction not met.")
        return True

    # Only media.play and media.stop are relevant for our workflow; ignore the rest.
    if payload.get("event") not in ("media.play", "media.stop"):
        logging.info("Skipping webhook: event '%s' is not media.play/media.stop.", payload.get("event"))
        return True

    media_type = (payload.get("Metadata") or {}).get("type")
    if media_type not in WEBHOOK_PLEX_PROCESS_MEDIA_TYPES:
        logging.info("Skipping webhook: media type '%s' is disabled.", media_type)
        return True

    return False


def build_thumb_url(library_partial_path: str | None) -> str | None:
    # Resolves a Plex-relative thumb path (e.g. "/library/metadata/123/thumb/456")
    # into a fully qualified URL against WEBHOOK_PLEX_SERVER_URL, authenticated with WEBHOOK_PLEX_TOKEN.
    if not library_partial_path or not WEBHOOK_PLEX_SERVER_URL:
        return None

    url = f"{WEBHOOK_PLEX_SERVER_URL}{library_partial_path}"
    if not WEBHOOK_PLEX_TOKEN:
        return url

    # Metadata paths from Plex never carry a query string of their own, so we can always append token once escaped.
    return f"{url}?X-Plex-Token={quote(WEBHOOK_PLEX_TOKEN, safe='')}"


def extract_media_poster(metadata: dict) -> tuple[str, str]:
    """Resolve a poster for the played item, falling back to its parent then grandparent art."""
    media_type = metadata.get("type") or "media"

    parent, grandparent = ANCESTOR_LABELS.get(media_type, ("parent", "grandparent"))
    level_prefix_name = [(parent, "parent"), (grandparent, "grandparent")]
    # Episode thumbs are preview frames and track thumbs are linked to their album, so we don't fetch their own thumb.
    if media_type not in ("episode", "track"):
        level_prefix_name.insert(0, (media_type, ""))

    for label, prefix in level_prefix_name:
        thumb_key, id_key = (f"{prefix}Thumb", f"{prefix}RatingKey") if prefix else ("thumb", "ratingKey")
        thumb_plex_partial_path = metadata.get(thumb_key)
        if thumb_plex_partial_path:
            logging.info("Poster from %s: title=%s", label, metadata.get("title"))
            return thumb_plex_partial_path, f"{label}_{metadata.get(id_key)}"

    raise LookupError(f"No poster found for media_type={media_type}")


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
