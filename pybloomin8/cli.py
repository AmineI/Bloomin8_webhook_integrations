"""Command-line entry point for temporary image display."""

import argparse
import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from .api import Bloomin8Api
from .constants import MANAGED_GALLERIES
from .workflow import TemporaryImageWorkflow


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Show a temporary image or restore the previous display."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    show_parser = commands.add_parser("show", help="Display an image after saving the current one")
    _add_mac_argument(show_parser)
    _add_ip_argument(show_parser)
    show_parser.add_argument("--image", required=True, type=Path, help="Image path")
    show_parser.add_argument(
        "--gallery",
        dest="gallery",
        required=True,
        help="Persistent destination gallery on the frame",
    )
    _add_managed_galleries_argument(show_parser)
    show_parser.add_argument(
        "--overwrite-state",
        action="store_true",
        default=False,
        help="Overwrite current saved state",
    )
    
    show_parser.add_argument(
        "--dither",
        type=int,
        default=None,
        help="Optional dither algorithm : 0 for Floyd-Steinberg (often better), 1 for faster JJN (often faster).",
    )
    show_parser.add_argument(
        "--fit-mode",
        dest="fit_mode",
        choices=["cover", "fit", "stretch"],
        default="cover",
        help="How to resize the image: cover (default, frame crops the overflow), fit (center-crop to panel size), or stretch.",
    )

    restore_parser = commands.add_parser(
        "restore",
        help="Restore the previous image displayed before the last set of show commands",
    )
    _add_mac_argument(restore_parser)
    _add_ip_argument(restore_parser)
    _add_managed_galleries_argument(restore_parser)
    restore_parser.add_argument(
        "--overwrite-state",
        action="store_true",
        default=False,
        help=(
            "Allow restore even when current display is outside managed galleries. "
            "By default restore is blocked to avoid overwriting non-managed content."
        ),
    )

    sleep_parser = commands.add_parser("sleep", help="Put the frame into sleep mode")
    _add_ip_argument(sleep_parser)

    delete_gallery_parser = commands.add_parser(
        "delete-gallery", help="Delete a gallery and all images within it"
    )
    _add_mac_argument(delete_gallery_parser)
    _add_ip_argument(delete_gallery_parser)
    _add_managed_galleries_argument(delete_gallery_parser)
    delete_gallery_parser.add_argument(
        "--gallery",
        required=True,
        help="Name of the gallery to delete",
    )
    return parser



def _add_managed_galleries_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--managed-galleries",
        default=None,
        help=(
            "Comma-separated gallery allowlist override for this command "
            "(for example: shows,posters). Overrides BLOOMIN8_MANAGED_GALLERIES."
        ),
    )



def _add_mac_argument(parser: argparse.ArgumentParser) -> None:
    env_mac = _env_value("BLOOMIN8_MAC", "MAC")
    parser.add_argument(
        "--mac",
        default=env_mac,
        required=env_mac is None,
        help="BLE MAC address (or set BLOOMIN8_MAC in .env)",
    )


def _add_ip_argument(parser: argparse.ArgumentParser) -> None:
    env_ip = _env_value("BLOOMIN8_IP", "IP")
    parser.add_argument(
        "--ip",
        default=env_ip,
        required=env_ip is None,
        help="Device LAN IP (or set BLOOMIN8_IP in .env)",
    )


def _env_value(*keys: str) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None


def _resolve_managed_galleries(args: argparse.Namespace) -> tuple[str, ...]:
    raw = getattr(args, "managed_galleries", None) or _env_value(
        "BLOOMIN8_MANAGED_GALLERIES",
    )
    if not raw:
        return MANAGED_GALLERIES

    # Lowercased so the comparison in is_managed_image, which lowercases device values, stays reliable.
    galleries = tuple(item.strip().lower() for item in raw.split(",") if item.strip())
    if not galleries:
        raise ValueError("at least one non-empty gallery is required")
    return galleries


async def run_from_args(args: argparse.Namespace) -> None:
    """Run the workflow represented by parsed CLI arguments."""
    if args.command == "sleep":
        async with Bloomin8Api(args.ip) as api:
            await api.sleep()
        return

    managed_galleries = _resolve_managed_galleries(args)

    if args.command == "delete-gallery":
        async with TemporaryImageWorkflow(args.mac, args.ip, managed_galleries) as workflow:
            await workflow.wake_and_connect()
            await workflow.api.delete_gallery(args.gallery)
        return

    async with TemporaryImageWorkflow(args.mac, args.ip, managed_galleries) as workflow:
        if args.command == "show":
            await workflow.replace_image_path(
                args.image,
                args.gallery,
                dither=args.dither,
                overwrite_state=args.overwrite_state,
                fit_mode=args.fit_mode,
            )
        else:
            await workflow.restore(overwrite_state=args.overwrite_state)


def main() -> None:
    """Parse arguments and run the temporary-image workflow."""
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    if args.command in ("show", "delete-gallery"):
        try:
            managed_galleries = _resolve_managed_galleries(args)
        except ValueError:
            parser.error(
                "Managed galleries override is empty. "
                "Use --managed-galleries with comma-separated values or set BLOOMIN8_MANAGED_GALLERIES."
            )

        if args.gallery.lower() not in managed_galleries:
            parser.error(
                f"Unsupported gallery '{args.gallery}'. "
                f"Allowed values: {', '.join(managed_galleries)}"
            )

    if args.command == "show" and not args.image.is_file():
        parser.error(f"Image not found: {args.image}")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    asyncio.run(run_from_args(args))