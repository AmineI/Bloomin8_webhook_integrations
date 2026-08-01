"""Persistent storage for display states awaiting manual restoration."""

import json
import logging
import re
from pathlib import Path
from typing import Any

from .constants import MANAGED_GALLERIES

STATE_DIRECTORY = Path(__file__).resolve().parent.parent / "bloomin8-state"
log = logging.getLogger(__name__)


def is_managed_display(state: dict[str, Any]) -> bool:
    """Return whether the current image belongs to a managed gallery."""
    gallery = str(state.get("gallery", "")).strip("/\\").lower()
    if gallery in MANAGED_GALLERIES:
        return True

    image_parts = str(state.get("image", "")).replace("\\", "/").split("/")
    return any(part.lower() in MANAGED_GALLERIES for part in image_parts[:-1])


class DisplayStateStore:
    """Persist one previous display state per frame."""

    def __init__(self, frame_id: str) -> None:
        safe_frame_id = re.sub(r"[^a-zA-Z0-9]+", "-", frame_id).strip("-").lower()
        self.path = STATE_DIRECTORY / f"{safe_frame_id}.json"

    @property
    def exists(self) -> bool:
        """Return whether this frame has a pending restoration."""
        return self.path.is_file()

    def save(self, state: dict[str, Any]) -> None:
        """Atomically save a display state."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        temporary_path.replace(self.path)

    def load(self) -> dict[str, Any]:
        """Load the display state or fail with an actionable message."""
        if not self.path.is_file():
            raise RuntimeError(
                "No previous display state is saved for this frame. "
                "Run the show command first."
            )
        return json.loads(self.path.read_text(encoding="utf-8"))

    def delete(self) -> None:
        """Delete a state after successful restoration."""
        self.path.unlink(missing_ok=True)

    def backup_current_state(
        self, current_state: dict[str, Any], overwrite_state: bool
    ) -> None:
        """Backup current state if unmanaged, respecting overwrite rules."""
        if not is_managed_display(current_state):
            # If the current image was not pushed by the script, we should try to keep it as a backup to restore.
            if self.exists and not overwrite_state:
                raise RuntimeError(
                    "The current image is outside the shows and games folders, "
                    "and saving it would overwrite the previous restoration state. "
                    "Use --overwrite-state to force."
                )
            else:
                log.info("Saved state will be overwritten with current frame state")
                self.save(current_state)
        else:
            log.info("Current image is from to the script-managed temp image gallery, no state saved")

    def load_and_delete(self) -> dict[str, Any]:
        """Load the saved state and delete the file in one operation."""
        state = self.load()
        self.delete()
        return state