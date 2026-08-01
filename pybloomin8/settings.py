"""Environment-driven configuration shared by the package."""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

from .constants import MANAGED_GALLERIES
from .image import FIT_MODES, FitMode


def env_value(*keys: str) -> str | None:
    """Return the first non-empty value among the given environment variables."""
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None


def parse_managed_galleries(raw: str | None) -> tuple[str, ...]:
    """Parse a comma-separated gallery allowlist, falling back to the defaults."""
    if not raw:
        return MANAGED_GALLERIES

    # Lowercased so the comparison in is_managed_image, which lowercases device values, stays reliable.
    galleries = tuple(item.strip().lower() for item in raw.split(",") if item.strip())
    if not galleries:
        raise ValueError("at least one non-empty gallery is required")
    return galleries


@dataclass(frozen=True)
class Settings:
    """Frame configuration resolved from the environment."""

    mac: str
    ip: str
    managed_galleries: tuple[str, ...]
    gallery: str
    fit_mode: FitMode

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        mac = env_value("BLOOMIN8_MAC", "MAC")
        ip = env_value("BLOOMIN8_IP", "IP")
        if not mac or not ip:
            raise RuntimeError(
                "Frame address missing. Set BLOOMIN8_MAC and BLOOMIN8_IP (or MAC and IP)."
            )

        managed_galleries = parse_managed_galleries(env_value("BLOOMIN8_MANAGED_GALLERIES"))

        gallery = (env_value("BLOOMIN8_GALLERY") or managed_galleries[0]).strip().lower()
        # Uploading outside the managed galleries would make a later restore refuse to run.
        if gallery not in managed_galleries:
            raise ValueError(
                f"BLOOMIN8_GALLERY '{gallery}' is not managed. "
                f"Allowed values: {', '.join(managed_galleries)}"
            )

        fit_mode = (env_value("BLOOMIN8_FIT_MODE") or "cover").strip().lower()
        if fit_mode not in FIT_MODES:
            raise ValueError(
                f"BLOOMIN8_FIT_MODE '{fit_mode}' is invalid. "
                f"Allowed values: {', '.join(FIT_MODES)}"
            )

        return cls(mac, ip, managed_galleries, gallery, fit_mode)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, reading the environment once."""
    return Settings.from_env()
