"""Environment-driven configuration shared by the package.

Every value resolves the same way: explicit override (CLI flag, HTTP parameter,
API argument) first, then the environment variable, then the package default.
"""

import os
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import cast

from .constants import (
    DEFAULT_DISPLAY_MODE,
    DEFAULT_EINK_PRESET,
    DEFAULT_MANAGED_GALLERIES,
    DEFAULT_ONLY_IF_IDLE
)
from . import eink
from .image import DISPLAY_MODES, DisplayMode


def env_value(*keys: str) -> str | None:
    """Return the first non-empty value among the given environment variables."""
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None


def resolve_mac(override: str | None = None) -> str:
    """Resolve the frame BLE MAC address."""
    mac = override or env_value("BLOOMIN8_MAC", "MAC")
    if not mac:
        raise ValueError("Frame MAC address missing. Pass --mac or set BLOOMIN8_MAC.")
    return mac.strip()


def resolve_ip(override: str | None = None) -> str:
    """Resolve the frame LAN IP address."""
    ip = override or env_value("BLOOMIN8_IP", "IP")
    if not ip:
        raise ValueError("Frame IP address missing. Pass --ip or set BLOOMIN8_IP.")
    return ip.strip()


def resolve_managed_galleries(override: str | None = None) -> tuple[str, ...]:
    """Resolve the comma-separated gallery allowlist."""
    raw = override or env_value("BLOOMIN8_MANAGED_GALLERIES")
    if not raw:
        return DEFAULT_MANAGED_GALLERIES

    # Lowercased so the comparison in is_managed_image, which lowercases device values, stays reliable.
    galleries = tuple(item.strip().lower() for item in raw.split(",") if item.strip())
    if not galleries:
        raise ValueError("Managed galleries list is empty. Provide comma-separated managed gallery names.")
    return galleries


def resolve_gallery(override: str | None, managed_galleries: tuple[str, ...]) -> str:
    """Resolve the destination gallery, which must belong to the given allowlist."""
    gallery = (override or env_value("BLOOMIN8_GALLERY") or managed_galleries[0]).strip().lower()
    # Uploading outside managed galleries would block restores, to avoid overriding a manually set picture.
    if gallery not in managed_galleries:
        raise ValueError(
            f"Gallery '{gallery}' is not managed. Allowed values: {', '.join(managed_galleries)}"
        )
    return gallery


def resolve_display_mode(override: str | None = None) -> DisplayMode:
    """Resolve how images are resized before upload."""
    display_mode = (override or env_value("BLOOMIN8_DISPLAY_MODE") or DEFAULT_DISPLAY_MODE).strip().lower()
    if display_mode not in DISPLAY_MODES:
        raise ValueError(
            f"Fit mode '{display_mode}' is invalid. Allowed values: {', '.join(DISPLAY_MODES)}"
        )
    return cast(DisplayMode, display_mode)


def resolve_only_if_idle(override: bool | None = None) -> bool:
    """Resolve whether a busy frame cancels the display instead of waiting for it."""
    if override is not None:
        return override
    raw = env_value("BLOOMIN8_ONLY_IF_IDLE")
    if raw is None:
        return DEFAULT_ONLY_IF_IDLE
    return raw.strip().lower() in ("true", "1", "yes")

def resolve_eink_optimization_preset(override: str | None = None) -> eink.EinkPreset:
    """Resolve the e-ink optimization preset used before upload."""
    preset = (override or env_value("BLOOMIN8_PYTHON_EINK_PRESET") or DEFAULT_EINK_PRESET).strip().lower().replace("_", "-")
    if preset not in eink.EINK_PRESETS:
        allowed = ", ".join(eink.EINK_PRESETS)
        raise ValueError(f"Unsupported e-ink preset '{preset}'. Allowed values: {allowed}")
    return cast(eink.EinkPreset, preset)

def resolve_debug_requests(override: bool | None = None) -> bool:
    """Resolve whether HTTP client debug logs should be enabled."""
    if override is not None:
        return override
    raw = env_value("BLOOMIN8_PYTHON_DEBUG_REQUESTS")
    if raw is None:
        return False
    return raw.strip().lower() in ("true", "1", "yes")

def configure_request_logging(debug_requests: bool) -> None:
    """Set HTTP client logger verbosity across common request stacks."""
    level = logging.INFO if debug_requests else logging.WARNING
    logging.getLogger("requests").setLevel(level)


@dataclass(frozen=True)
class Settings:
    """Frame configuration resolved from overrides and the environment."""

    mac: str
    ip: str
    managed_galleries: tuple[str, ...]
    gallery: str
    display_mode: DisplayMode
    only_if_idle: bool
    eink_optimization_preset: eink.EinkPreset
    debug_requests: bool

    @classmethod
    def resolve(
        cls,
        *,
        mac: str | None = None,
        ip: str | None = None,
        managed_galleries: str | None = None,
        gallery: str | None = None,
        display_mode: str | None = None,
        only_if_idle: bool | None = None,
        eink_optimization_preset: str | None = None,
        debug_requests: bool | None = None,
    ) -> "Settings":
        """Build settings, letting the given overrides win over the environment."""
        resolved_mgd_galleries = resolve_managed_galleries(managed_galleries)
        return cls(
            mac=resolve_mac(mac),
            ip=resolve_ip(ip),
            managed_galleries=resolved_mgd_galleries,
            gallery=resolve_gallery(gallery, resolved_mgd_galleries),
            display_mode=resolve_display_mode(display_mode),
            only_if_idle=resolve_only_if_idle(only_if_idle),
            eink_optimization_preset=resolve_eink_optimization_preset(eink_optimization_preset),
            debug_requests=resolve_debug_requests(debug_requests),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, reading the environment once."""
    settings = Settings.resolve()
    configure_request_logging(settings.debug_requests)
    return settings
