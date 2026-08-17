"""Environment-driven configuration for the webhook hosts."""

import os

from dotenv import load_dotenv

import pybloomin8
from pybloomin8.settings import resolve_display_mode

load_dotenv()
# An invalid frame configuration must fail at startup, not mid-webhook.
pybloomin8.get_settings()


def env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in ("true", "1", "yes")

WEBHOOK_PLEX_SERVER_URL = os.getenv("WEBHOOK_PLEX_SERVER_URL", "").strip().rstrip("/")
WEBHOOK_PLEX_TOKEN = os.getenv("WEBHOOK_PLEX_TOKEN", "")
REQUIRE_OWNER_PLAYBACK = env_flag("WEBHOOK_PROCESS_OWNER_PLAYBACK_ONLY", "true")
REQUIRE_LOCAL_PLAYER = env_flag("WEBHOOK_PROCESS_LOCAL_PLAYBACK_ONLY", "true")
WEBHOOK_LISTEN_FOR_PLEX_MEDIA_TYPES = tuple(
    media_type.strip().lower()
    for media_type in os.getenv(
        "WEBHOOK_LISTEN_FOR_PLEX_MEDIA_TYPES", "movie,episode"
    ).split(",")
    if media_type.strip()
)
# Ignore media.stop events when false, leaving the temporary image displayed.
WEBHOOK_LISTEN_FOR_PLEX_STOP = env_flag("WEBHOOK_LISTEN_FOR_PLEX_STOP", "true")
# Lets the Plex webhook restore an image to a frame showing an image it did not put there.
WEBHOOK_DEFAULT_OVERWRITE_STATE = env_flag("WEBHOOK_DEFAULT_OVERWRITE_STATE", "false")
# Skips the poster instead of queuing behind whatever the frame is already doing.
WEBHOOK_ACTION_ONLY_IF_IDLE = env_flag("WEBHOOK_ACTION_ONLY_IF_IDLE", "true")

#Skipping through media would otherwise send a display & upload per event.
WEBHOOK_RESTORE_DEBOUNCE_SECONDS = int(os.getenv("WEBHOOK_RESTORE_DEBOUNCE_SECONDS", "25"))
WEBHOOK_SHOW_DEBOUNCE_SECONDS = int(os.getenv("WEBHOOK_SHOW_DEBOUNCE_SECONDS", "5"))

TRACK_DISPLAY_MODE = resolve_display_mode(os.getenv("TRACK_DISPLAY_MODE", "vibrant-popout"))
BLOOMIN8_DISPLAY_MODE = resolve_display_mode(os.getenv("BLOOMIN8_DISPLAY_MODE", "cover"))


POSTER_DOWNLOAD_TIMEOUT_SECONDS = 20.0
POSTER_MAX_BYTES = 16 * 1024 * 1024
BLOOMIN8_MEDIA_POSTER_GALLERY = "media"
BLOOMIN8_MUSIC_ART_GALLERY = "music"


