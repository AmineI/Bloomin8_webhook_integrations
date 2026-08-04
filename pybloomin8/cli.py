"""Command-line entry point for temporary image display."""

import argparse
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

from .api import Bloomin8Api
from .image import DISPLAY_MODES
from .settings import Settings, configure_request_logging, resolve_ip
from .workflow import TemporaryImageWorkflow


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Options default to None so that anything left unset is resolved from the
    environment by Settings, keeping one resolution order for CLI and service.
    """
    ip_option = argparse.ArgumentParser(add_help=False)
    ip_option.add_argument("--ip", help="Device LAN IP (default: BLOOMIN8_IP)")

    frame_options = argparse.ArgumentParser(add_help=False, parents=[ip_option])
    frame_options.add_argument("--mac", help="BLE MAC address (default: BLOOMIN8_MAC)")
    frame_options.add_argument(
        "--managed-galleries",
        help=(
            "Comma-separated gallery allowlist for this command "
            "(for example: media,posters,temp). Default: BLOOMIN8_MANAGED_GALLERIES."
        ),
    )

    parser = argparse.ArgumentParser(
        description="Show a temporary image or restore the previous display."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    show_parser = commands.add_parser(
        "show",
        parents=[frame_options],
        help="Display an image after saving the current one",
    )
    show_parser.add_argument("--image", required=True, type=Path, help="Image path")
    show_parser.add_argument(
        "--gallery",
        help="Persistent destination gallery on the frame (default: BLOOMIN8_GALLERY)",
    )
    show_parser.add_argument(
        "--overwrite-state", action="store_true", help="Overwrite current saved state"
    )
    show_parser.add_argument(
        "--only-if-idle",
        action=argparse.BooleanOptionalAction,
        help=(
            "Cancel instead of waiting when the frame is already busy "
            "(default: BLOOMIN8_ONLY_IF_IDLE, else off)."
        ),
    )
    show_parser.add_argument(
        "--dither",
        type=int,
        help="Optional dither algorithm : 0 for Floyd-Steinberg (often better), 1 for faster JJN (often faster).",
    )
    show_parser.add_argument(
        "--display-mode",
        choices=list(DISPLAY_MODES),
        help="How to resize the image, described in the README (default: BLOOMIN8_DISPLAY_MODE, else cover).",
    )

    restore_parser = commands.add_parser(
        "restore",
        parents=[frame_options],
        help="Restore the previous image displayed before the last set of show commands",
    )
    restore_parser.add_argument(
        "--overwrite-state",
        action="store_true",
        help=(
            "Allow restore even when current display is outside managed galleries. "
            "By default restore is blocked to avoid overwriting non-managed content."
        ),
    )

    commands.add_parser("sleep", parents=[ip_option], help="Put the frame into sleep mode")

    delete_gallery_parser = commands.add_parser(
        "delete-gallery",
        parents=[frame_options],
        help="Delete a gallery and all images within it",
    )
    delete_gallery_parser.add_argument(
        "--gallery", required=True, help="Name of the gallery to delete"
    )
    return parser


async def sleep_frame(ip: str) -> None:
    """Send the frame to sleep."""
    async with Bloomin8Api(ip) as api:
        await api.sleep()


async def run_from_args(args: argparse.Namespace, settings: Settings) -> None:
    """Run the workflow represented by parsed CLI arguments."""
    async with TemporaryImageWorkflow(
        settings.mac, settings.ip, settings.managed_galleries
    ) as workflow:
        if args.command == "show":
            await workflow.replace_image_path(
                args.image,
                settings.gallery,
                dither=args.dither,
                overwrite_state=args.overwrite_state,
                display_mode=settings.display_mode,
                only_if_idle=settings.only_if_idle,
            )
        elif args.command == "delete-gallery":
            await workflow.wake_and_connect()
            await workflow.api.delete_gallery(settings.gallery)
        else:
            await workflow.restore(overwrite_state=args.overwrite_state)


def main() -> None:
    """Parse arguments and run the temporary-image workflow."""
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.command == "sleep":
        try:
            ip = resolve_ip(args.ip)
        except ValueError as error:
            parser.error(str(error))
        asyncio.run(sleep_frame(ip))
        return

    if args.command == "show" and not args.image.is_file():
        parser.error(f"Image not found: {args.image}")

    try:
        settings = Settings.resolve(
            mac=args.mac,
            ip=args.ip,
            managed_galleries=args.managed_galleries,
            gallery=getattr(args, "gallery", None),
            display_mode=getattr(args, "display_mode", None),
            only_if_idle=getattr(args, "only_if_idle", None),
        )
        configure_request_logging(settings.debug_requests)
    except ValueError as error:
        parser.error(str(error))

    asyncio.run(run_from_args(args, settings))