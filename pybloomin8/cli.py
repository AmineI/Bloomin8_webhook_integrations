"""Command-line entry point for temporary image display."""

import argparse
import asyncio
import logging
from pathlib import Path

from .constants import MANAGED_GALLERIES
from .workflow import TemporaryImageWorkflow


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Show a temporary image or restore the previous display."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    show_parser = commands.add_parser("show", help="Display an image after saving the current one")
    _add_frame_arguments(show_parser)
    show_parser.add_argument("--image", required=True, type=Path, help="Image path")
    show_parser.add_argument(
        "--folder",
        required=True,
        choices=MANAGED_GALLERIES,
        help="Persistent destination folder on the frame",
    )
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

    restore_parser = commands.add_parser(
        "restore",
        help="Restore the previous image displayed before the last set of show commands",
    )
    _add_frame_arguments(restore_parser)
    return parser


def _add_frame_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mac", required=True, help="BLE MAC address")
    parser.add_argument("--ip", required=True, help="Device LAN IP")


async def run_from_args(args: argparse.Namespace) -> None:
    """Run the workflow represented by parsed CLI arguments."""
    async with TemporaryImageWorkflow(args.mac, args.ip) as workflow:
        if args.command == "show":
            await workflow.replace_image(
                args.image,
                args.folder,
                dither=args.dither,
                overwrite_state=args.overwrite_state,
            )
        else:
            await workflow.restore()


def main() -> None:
    """Parse arguments and run the temporary-image workflow."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "show" and not args.image.is_file():
        parser.error(f"Image not found: {args.image}")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    asyncio.run(run_from_args(args))