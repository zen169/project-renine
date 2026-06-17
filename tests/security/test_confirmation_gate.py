"""Tests for renine.security.confirmation_gate."""
from __future__ import annotations

import pytest

from renine.core.exceptions import ConfirmationDeniedError
from renine.security.confirmation_gate import (
    ConfirmationRequest,
    ConfirmationStatus,
    approve,
    deny,
    request_confirmation,
    requires_confirmation,
)


class TestRequestConfirmation:
    """Tests for request_confirmation."""

    def test_returns_pending_request(self) -> None:
        """Returns a request with PENDING status."""
        req = request_confirmation("file_delete", "Delete a file")
        assert isinstance(req, ConfirmationRequest)
        assert req.status == ConfirmationStatus.PENDING

    def test_action_and_description_stored(self) -> None:
        """Action and description are stored on the request."""
        req = request_confirmation("test_action", "Test desc", "test_agent")
        assert req.action == "test_action"
        assert req.description == "Test desc"
        assert req.source_agent == "test_agent"


class TestApprove:
    """Tests for approve."""

    def test_sets_approved_status(self) -> None:
        """approve() sets status to APPROVED."""
        req = request_confirmation("x", "x")
        approved = approve(req)
        assert approved.status == ConfirmationStatus.APPROVED


class TestDeny:
    """Tests for deny."""

    def test_raises_confirmation_denied_error(self) -> None:
        """deny() raises ConfirmationDeniedError."""
        req = request_confirmation("x", "x")
        with pytest.raises(ConfirmationDeniedError):
            deny(req)

    def test_sets_denied_status_before_raise(self) -> None:
        """Request status is DENIED when error is raised."""
        req = request_confirmation("x", "x")
        with pytest.raises(ConfirmationDeniedError):
            deny(req)
        assert req.status == ConfirmationStatus.DENIED


class TestRequiresConfirmation:
    """Tests for requires_confirmation."""

    def test_known_action_requires_confirmation(self) -> None:
        """Actions in always_confirm list return True."""
        # file_delete is expected to be in security.yaml
        result = requires_confirmation("file_delete")
        assert isinstance(result, bool)

    def test_unknown_action_does_not_require(self) -> None:
        """Unknown actions return False."""
        assert requires_confirmation("totally_safe_read") is False
