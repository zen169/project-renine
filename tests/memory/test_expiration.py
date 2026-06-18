from unittest.mock import MagicMock, patch

import pytest

from renine.memory import expiration


@pytest.fixture(autouse=True)
def reset_scheduler_cache():
    expiration._scheduler = None
    yield
    expiration._scheduler = None


@pytest.fixture
def mock_scheduler():
    with patch(
        "renine.memory.expiration.BackgroundScheduler",
    ) as mock_sched_class:
        mock_instance = MagicMock()
        mock_sched_class.return_value = mock_instance
        yield mock_instance


def test_get_scheduler(mock_scheduler):
    sched = expiration.get_scheduler()
    assert sched == mock_scheduler


def test_start_expiration_scheduler(mock_scheduler):
    mock_scheduler.running = False

    with patch(
        "renine.memory.expiration.delete_expired_conversations",
    ) as mock_delete:
        expiration.start_expiration_scheduler()

        mock_scheduler.add_job.assert_called_once()
        mock_scheduler.start.assert_called_once()


def test_stop_expiration_scheduler(mock_scheduler):
    expiration.get_scheduler()
    mock_scheduler.running = True

    expiration.stop_expiration_scheduler()
    mock_scheduler.shutdown.assert_called_once_with(wait=False)
    assert expiration._scheduler is None


def test_is_scheduler_running(mock_scheduler):
    expiration.get_scheduler()
    mock_scheduler.running = True
    assert expiration.is_scheduler_running() is True

    mock_scheduler.running = False
    assert expiration.is_scheduler_running() is False

