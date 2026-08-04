"""Debounced scheduling of a single pending action, shared by the HTTP triggers."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

# Frame actions are mutually exclusive, so one pending task covers all of them.
# It is held in a module global so it survives the response that scheduled it.
_pending: asyncio.Task | None = None


def schedule(action: Callable[[], Awaitable[object]], delay: int) -> asyncio.Task:
    """Run the action once the delay elapses, replacing whatever action was still pending."""
    global _pending

    # cancel() returns False when the action already ran, so this only logs real cancellations.
    if _pending is not None and _pending.cancel():
        logging.info("Pending action cancelled by a newer event.")

    logging.info("Action scheduled in %ss.", delay)
    _pending = asyncio.create_task(_run_later(action, delay))
    return _pending


async def wait_for_result(task: asyncio.Task, action: str) -> tuple[str, int]:
    """Wait for a scheduled task, returning its outcome as a message and an HTTP status code."""
    # Waiting inside the invocation stops the Functions host from tearing the worker down mid-debounce.
    # asyncio.wait() returns instead of raising when a newer event cancels the task.
    await asyncio.wait({task})

    if task.cancelled():
        return f"{action} cancelled by a newer event.", 200

    error = task.exception()
    if error is not None:
        logging.error("%s failed.", action, exc_info=error)
        return f"{action} failed: {error}", 500

    return "OK", 200


async def _run_later(action: Callable[[], Awaitable[object]], delay: int) -> object:
    global _pending

    await asyncio.sleep(delay)

    # Past the window the action is committed; a later event must not interrupt it.
    _pending = None

    logging.info("Debounce delay elapsed : running pending action")
    return await action()
