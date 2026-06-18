"""Background worker to enforce conversation history expiration (TTL).

Uses APScheduler to run periodic cleanups in history.db according to settings.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from renine.core.config import get_memory_config
from renine.memory.layer2_history import delete_expired_conversations

logger = logging.getLogger("renine.memory.expiration")

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    """Get or create the background scheduler.

    Returns:
        The BackgroundScheduler instance.
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(daemon=True)
    return _scheduler


def _run_cleanup() -> None:
    """Job function to delete expired conversation history."""
    try:
        config = get_memory_config()
        ttl_hours = (
            config.get("memory", {}).get("layer2", {}).get("ttl_hours", 48)
        )
        logger.debug(
            "Running conversation expiration cleanup with TTL = %d hours",
            ttl_hours,
        )
        deleted = delete_expired_conversations(ttl_hours=ttl_hours)
        if deleted > 0:
            logger.info(
                "Expiration cleanup removed %d old conversation sessions",
                deleted,
            )
    except Exception as e:
        logger.error(
            "Error during history expiration cleanup job: %s",
            e,
            exc_info=True,
        )


def start_expiration_scheduler() -> None:
    """Start the periodic conversation cleanup scheduler."""
    scheduler = get_scheduler()
    if scheduler.running:
        logger.warning("Expiration scheduler is already running")
        return

    config = get_memory_config()
    interval_mins = (
        config.get("memory", {})
        .get("layer2", {})
        .get("cleanup_interval_minutes", 60)
    )

    scheduler.add_job(
        _run_cleanup,
        "interval",
        minutes=interval_mins,
        id="history_ttl_cleanup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Started history expiration scheduler. Cleanup interval: %d minutes",
        interval_mins,
    )


def stop_expiration_scheduler() -> None:
    """Stop the background cleanup scheduler."""
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        logger.debug("Expiration scheduler is not running")
        return

    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Stopped history expiration scheduler")


def is_scheduler_running() -> bool:
    """Check if the expiration scheduler is currently running.

    Returns:
        True if running, else False.
    """
    if _scheduler is None:
        return False
    return _scheduler.running
