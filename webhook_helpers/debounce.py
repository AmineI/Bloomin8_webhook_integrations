"""Debounced scheduling of a single pending action, shared by the HTTP triggers."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

# Frame actions are mutually exclusive, so one pending task covers all of them.
# It is held in a module global so it survives the response that scheduled it.
_pending: asyncio.Task | None = None


def schedule(
    action: Callable[[], Awaitable[object]],
    delay: int,
    during_delay: Callable[[], Awaitable[object]] | None = None,
) -> asyncio.Task:
    """Run the action after the delay, optionally running work in parallel during the wait."""
    global _pending

    # cancel() returns False when the action already ran, so this only logs real cancellations.
    if _pending is not None and _pending.cancel():
        logging.info("Pending action cancelled by a newer event.")

    logging.info("Action scheduled in %ss.", delay)
    _pending = asyncio.create_task(_run_later(action, delay, during_delay))
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


async def _run_later(
    action: Callable[[], Awaitable[object]],
    delay: int,
    during_delay: Callable[[], Awaitable[object]] | None = None,
) -> object:
    global _pending

    during_task: asyncio.Task | None = None
    if during_delay is not None:
        during_task = asyncio.create_task(during_delay())

    await asyncio.sleep(delay)

    if during_task is not None:
        try:
            # Keep this work alive even if a newer event cancels the debounced action task.
            await asyncio.shield(during_task)
        except Exception:
            logging.warning("During-delay action failed.", exc_info=True)

    # Past the window the action is committed; a later event must not interrupt it.
    _pending = None

    logging.info("Debounce delay elapsed : running pending action")
    return await action()
