"""Tests for renine.agents.email_agent — Email Agent.

Validates:
- Inbox messages can be listed using mock/real API client.
- Reply draft creation works.
- Explicit blocking of direct email send operations.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from renine.agents.email_agent import (
    GMAIL_COMPOSE_SCOPE,
    GMAIL_READONLY_SCOPE,
    GMAIL_SEND_SCOPE,
    SCOPES,
    EmailAgent,
)


class TestEmailAgent:
    """Tests for the EmailAgent implementation."""

    def test_default_scopes_are_readonly_only(self) -> None:
        """Default Gmail OAuth scopes are readonly only."""
        assert SCOPES == [GMAIL_READONLY_SCOPE]

    def test_compose_scope_absent_by_default(self) -> None:
        """Gmail compose scope is not requested unless explicitly escalated."""
        agent = EmailAgent()

        assert GMAIL_COMPOSE_SCOPE not in SCOPES
        assert agent._get_gmail_scopes() == [GMAIL_READONLY_SCOPE]
        assert GMAIL_COMPOSE_SCOPE in agent._get_gmail_scopes(include_compose=True)
        assert GMAIL_SEND_SCOPE not in agent._get_gmail_scopes(include_compose=True)

    @patch("renine.agents.email_agent.EmailAgent._get_gmail_service")
    def test_list_messages_mock_service(self, mock_get_service: MagicMock) -> None:
        """If Gmail service is not authenticated, returns default mock inbox list."""
        mock_get_service.return_value = None  # No credentials / token available
        
        agent = EmailAgent()
        result = agent.process("list my email")
        
        assert result["success"] is True
        assert result["source_agent"] == "email"
        assert "Project Renine Phase 5 Status" in result["content"]
        assert len(result["messages"]) == 2

    @patch("renine.agents.email_agent.EmailAgent._get_gmail_service")
    def test_list_messages_authenticated_service(self, mock_get_service: MagicMock) -> None:
        """If Gmail service is authenticated, fetches and parses live inbox list."""
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service

        # Mock the chain of calls service.users().messages().list().execute()
        mock_messages_resource = mock_service.users.return_value.messages.return_value
        mock_messages_resource.list.return_value.execute.return_value = {
            "messages": [{"id": "msg123"}]
        }
        
        # Mock the get message metadata call
        mock_messages_resource.get.return_value.execute.return_value = {
            "id": "msg123",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "test@domain.com"},
                    {"name": "Date", "value": "Wed, 17 Jun 2026 12:00:00"},
                ]
            }
        }

        agent = EmailAgent()
        result = agent.process("list my inbox")
        
        assert result["success"] is True
        assert "Test Subject" in result["content"]
        assert "test@domain.com" in result["content"]
        assert result["messages"][0]["id"] == "msg123"

    @patch("renine.agents.email_agent.EmailAgent._get_gmail_service")
    def test_create_draft_flow(self, mock_get_service: MagicMock) -> None:
        """Creating an email draft calls the Gmail API drafts resource correctly."""
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        mock_drafts_resource = mock_service.users.return_value.drafts.return_value
        mock_drafts_resource.create.return_value.execute.return_value = {"id": "real_draft_999"}

        agent = EmailAgent()
        # Trigger draft action by keywords
        with patch.object(agent, "_draft_creation_enabled", return_value=True):
            result = agent.process("draft an email to boss@example.com subject Hello body test body")
        
        assert result["success"] is True
        assert "Draft email successfully created" in result["content"]
        assert result["draft_id"] == "real_draft_999"
        mock_drafts_resource.create.assert_called_once()
        assert mock_get_service.call_args.kwargs["scopes"] == [
            GMAIL_READONLY_SCOPE,
            GMAIL_COMPOSE_SCOPE,
        ]

    @patch("renine.agents.email_agent.EmailAgent._get_gmail_service")
    def test_create_draft_blocked_by_default(self, mock_get_service: MagicMock) -> None:
        """Draft creation is blocked unless configuration explicitly enables compose access."""
        agent = EmailAgent()

        result = agent.process("draft an email to boss@example.com")

        assert result["success"] is False
        assert "draft creation is disabled by default" in result["content"]
        mock_get_service.assert_not_called()

    def test_send_email_blocked_by_policy(self) -> None:
        """Sending an email is blocked by default and outputs security explanation."""
        agent = EmailAgent()
        result = agent.process("send email to client@example.com")
        
        assert result["success"] is False
        assert "Security Policy Restriction" in result["content"]
        assert "Direct email sending is disabled" in result["content"]
        assert GMAIL_SEND_SCOPE not in SCOPES
