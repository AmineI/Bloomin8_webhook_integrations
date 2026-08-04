"""Environment-driven configuration for the Azure Function app."""

import os

from dotenv import load_dotenv

import pybloomin8

load_dotenv()
# An invalid frame configuration must fail at startup, not mid-webhook.
pybloomin8.get_settings()


def env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in ("true", "1", "yes")

TRACK_DISPLAY_MODE = os.getenv("TRACK_DISPLAY_MODE", "vibrant-popout")

PLEX_SERVER_URL = os.getenv("PLEX_SERVER_URL", "").strip().rstrip("/")
PLEX_TOKEN = os.getenv("PLEX_TOKEN", "")
REQUIRE_OWNER_PLAYBACK = env_flag("PROCESS_OWNER_PLAYBACK_ONLY", "true")
REQUIRE_LOCAL_PLAYER = env_flag("PROCESS_LOCAL_PLAYBACK_ONLY", "true")
# Lets the Plex webhook restore an image to a frame showing an image it did not put there.
PLEX_OVERWRITE_STATE = env_flag("PLEX_OVERWRITE_STATE", "false")
# Skips the poster instead of queuing behind whatever the frame is already doing.
PLEX_ACTION_ONLY_IF_IDLE = env_flag("PLEX_ACTION_ONLY_IF_IDLE", "true")

#Skipping through media would otherwise send a display & upload per event.
RESTORE_DEBOUNCE_SECONDS = int(os.getenv("RESTORE_DEBOUNCE_SECONDS", "25"))
SHOW_DEBOUNCE_SECONDS = int(os.getenv("SHOW_DEBOUNCE_SECONDS", "5"))

POSTER_DOWNLOAD_TIMEOUT_SECONDS = 20.0
POSTER_MAX_BYTES = 16 * 1024 * 1024
BLOOMIN8_MEDIA_POSTER_GALLERY = "media"


