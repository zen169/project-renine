"""Tests for renine.brain.response_builder — response assembly."""
from __future__ import annotations

from renine.brain.response_builder import (
    RenineResponse,
    ResponseType,
    build_confirmation_response,
    build_error_response,
    build_text_response,
    build_tool_result_response,
)


class TestBuildTextResponse:
    """Tests for build_text_response."""

    def test_returns_renine_response(self) -> None:
        """Returns a RenineResponse object."""
        r = build_text_response("Hello")
        assert isinstance(r, RenineResponse)

    def test_correct_type(self) -> None:
        """Type is ResponseType.TEXT."""
        r = build_text_response("Hello")
        assert r.response_type == ResponseType.TEXT

    def test_content_preserved(self) -> None:
        """Content is stored as-is."""
        r = build_text_response("Hello world")
        assert r.content == "Hello world"

    def test_default_source_agent(self) -> None:
        """Default source_agent is 'main_brain'."""
        r = build_text_response("Hi")
        assert r.source_agent == "main_brain"

    def test_speak_default_true(self) -> None:
        """speak defaults to True."""
        r = build_text_response("Hi")
        assert r.speak is True


class TestBuildErrorResponse:
    """Tests for build_error_response."""

    def test_error_type(self) -> None:
        """Type is ResponseType.ERROR."""
        r = build_error_response("something broke")
        assert r.response_type == ResponseType.ERROR

    def test_user_friendly_message(self) -> None:
        """Custom user_friendly message is used in content."""
        r = build_error_response("internal", user_friendly="Oops!")
        assert r.content == "Oops!"

    def test_default_message_when_no_friendly(self) -> None:
        """Default message used when user_friendly is None."""
        r = build_error_response("error detail")
        assert "try again" in r.content.lower()

    def test_technical_error_in_metadata(self) -> None:
        """Technical error stored in metadata, not exposed as content."""
        r = build_error_response("secret stack trace")
        assert r.metadata.get("technical_error") == "secret stack trace"


class TestBuildConfirmationResponse:
    """Tests for build_confirmation_response."""

    def test_confirmation_type(self) -> None:
        """Type is ResponseType.CONFIRMATION_REQUEST."""
        r = build_confirmation_response("Are you sure?", "Delete file")
        assert r.response_type == ResponseType.CONFIRMATION_REQUEST

    def test_pending_action_in_metadata(self) -> None:
        """Pending action is stored in metadata."""
        r = build_confirmation_response("Sure?", "Delete file")
        assert r.metadata.get("pending_action") == "Delete file"


class TestBuildToolResultResponse:
    """Tests for build_tool_result_response."""

    def test_tool_result_type(self) -> None:
        """Type is ResponseType.TOOL_RESULT."""
        r = build_tool_result_response("Done", [{"tool": "alarm", "status": "ok"}])
        assert r.response_type == ResponseType.TOOL_RESULT

    def test_tool_results_attached(self) -> None:
        """Tool results are attached to the response."""
        results = [{"tool": "alarm", "ok": True}]
        r = build_tool_result_response("Done", results)
        assert r.tool_results == results
