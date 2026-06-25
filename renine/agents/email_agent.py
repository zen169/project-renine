"""Email agent for Renine.

Integrates with Gmail API using OAuth2 to retrieve messages and optionally create drafts.
Enforces strict security constraints: scopes are readonly by default, draft creation
requires explicit configuration, and the send permission is disabled.

============================================================
GMAIL OAUTH2 CONSENT FLOW DOCUMENTATION
============================================================
1. Setup Google Cloud Project:
   - Go to Google Cloud Console (https://console.cloud.google.com).
   - Create a new project named 'Project Renine'.
   - Enable 'Gmail API' under APIs & Services.

2. Configure OAuth Consent Screen:
   - Navigate to 'OAuth consent screen' section.
   - Choose User Type 'External' (or 'Internal' if using a Google Workspace organization).
   - Fill out app metadata (App name, support email, developer contact details).
   - In the Scopes screen, add the default scope:
     - `https://www.googleapis.com/auth/gmail.readonly` (Read message metadata and body)
   - Only add `https://www.googleapis.com/auth/gmail.compose` if draft creation is explicitly
     enabled in configuration.
   - Do NOT add `https://www.googleapis.com/auth/gmail.send` (Send emails).
   - Add your Gmail address as a 'Test user'.

3. Create Credentials:
   - Go to 'Credentials' section.
   - Click 'Create Credentials' > 'OAuth client ID'.
   - Select application type 'Desktop app' and click Create.
   - Download the JSON credentials file and save it as `credentials.json` in the project root folder.

4. Authorization Consent Flow:
   - On first execution, the Python backend will open a local browser window to Google's consent screen.
   - Log in using your registered Test user Google Account.
   - Review permissions (read-only access by default).
   - Accept the consent screen. The token will be saved to `token.json` for subsequent silent authentication.
"""
from __future__ import annotations

import base64
import os
from email.mime.text import MIMEText
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from renine.agents.base_agent import AgentManifest, BaseAgent, MemoryAccessLevel
from renine.core.config import get_settings
from renine.core.logging_config import get_logger
from renine.tools.permissions import PermissionLevel

logger = get_logger(__name__)

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"

# Security limit: default OAuth is readonly only. Compose is opt-in; send is never used.
SCOPES = [GMAIL_READONLY_SCOPE]


class EmailAgent(BaseAgent):
    """Agent that manages Gmail reading and drafting, enforcing OAuth2 scope boundaries."""

    def get_manifest(self) -> AgentManifest:
        """Return the capability manifest for EmailAgent."""
        return AgentManifest(
            name="email",
            description="Manages Gmail reading and drafting replies",
            required_tools=[],
            memory_access_level=MemoryAccessLevel.LAYER1_ONLY,
            permission_level=PermissionLevel.STANDARD,
            active_phase=6,
        )

    def _get_gmail_scopes(self, include_compose: bool = False) -> list[str]:
        """Return Gmail OAuth scopes for the requested capability level.

        Args:
            include_compose: Whether to include draft-creation scope.

        Returns:
            List of OAuth scopes. The send scope is never included.
        """
        scopes = [GMAIL_READONLY_SCOPE]
        if include_compose:
            scopes.append(GMAIL_COMPOSE_SCOPE)
        return scopes

    def _draft_creation_enabled(self) -> bool:
        """Return whether Gmail draft creation has been explicitly enabled."""
        settings = get_settings()
        return bool(settings.get("email", {}).get("allow_draft_creation", False))

    def _get_gmail_service(self, scopes: list[str] | None = None) -> Any:
        """Authenticate and return the Gmail API client.

        Args:
            scopes: OAuth scopes for this Gmail session.

        Returns:
            Gmail service resource client, or None if in mock/test mode.
        """
        active_scopes = scopes or self._get_gmail_scopes()

        # If credentials.json is not present, we default to mock mode automatically
        if not os.path.exists("credentials.json") and not os.path.exists("token.json"):
            logger.warning("gmail_credentials_missing_using_mock_mode")
            return None

        creds = None
        if os.path.exists("token.json"):
            try:
                creds = Credentials.from_authorized_user_file("token.json", active_scopes)
            except Exception as e:
                logger.error("invalid_token_file", error=str(e))

        # Perform authentication flow if credentials are not valid/expired
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    logger.warning("refresh_token_expired_reauthenticating")
                    creds = None
            
            if not creds:
                if not os.path.exists("credentials.json"):
                    return None
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json",
                    active_scopes,
                )
                creds = flow.run_local_server(port=0)
                
            # Save token for next run
            with open("token.json", "w") as token:
                token.write(creds.to_json())

        try:
            return build("gmail", "v1", credentials=creds)
        except Exception as e:
            logger.error("gmail_service_build_failed", error=str(e))
            return None

    def _list_messages(self, service: Any, max_results: int = 5) -> list[dict[str, Any]]:
        """List recent messages from the inbox.

        Args:
            service: Gmail API service object.
            max_results: Max message details to fetch.

        Returns:
            List of message dicts with metadata.
        """
        if service is None:
            # Return Mock Data
            return [
                {
                    "id": "mock_msg_1",
                    "subject": "Project Renine Phase 5 Status",
                    "from": "manager@renine.local",
                    "date": "2026-06-18 10:00",
                },
                {
                    "id": "mock_msg_2",
                    "subject": "Playwright dependencies warning",
                    "from": "security@renine.local",
                    "date": "2026-06-18 09:30",
                },
            ]

        try:
            results = service.users().messages().list(userId="me", maxResults=max_results).execute()
            messages = results.get("messages", [])
            
            detailed_messages = []
            for msg in messages:
                msg_id = msg["id"]
                msg_detail = service.users().messages().get(userId="me", id=msg_id, format="metadata").execute()
                
                headers = msg_detail.get("payload", {}).get("headers", [])
                subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "(No Subject)")
                sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "Unknown")
                date = next((h["value"] for h in headers if h["name"].lower() == "date"), "")

                detailed_messages.append({
                    "id": msg_id,
                    "subject": subject,
                    "from": sender,
                    "date": date,
                })
            return detailed_messages
        except Exception as e:
            logger.error("gmail_list_messages_failed", error=str(e))
            return []

    def _create_draft(self, service: Any, to: str, subject: str, body: str) -> dict[str, Any]:
        """Create a draft message.

        Args:
            service: Gmail API service.
            to: Recipient email address.
            subject: Email subject.
            body: Email body.

        Returns:
            Dictionary containing result metadata.
        """
        if service is None:
            # Return Mock Result
            return {
                "success": True,
                "draft_id": "mock_draft_123",
                "message": f"Mock draft created successfully. To: {to}, Subject: {subject}",
            }

        try:
            message = MIMEText(body)
            message["to"] = to
            message["from"] = "me"
            message["subject"] = subject
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            
            body_payload = {"message": {"raw": raw_message}}
            
            draft = service.users().drafts().create(userId="me", body=body_payload).execute()
            logger.info("gmail_draft_created", draft_id=draft.get("id"))
            return {
                "success": True,
                "draft_id": draft.get("id"),
                "message": "Draft email successfully created in your Gmail account.",
            }
        except Exception as e:
            logger.error("gmail_create_draft_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    def process(
        self,
        user_input: str,
        context: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process email commands: list inbox, read messages, create drafts, reject send commands.

        Args:
            user_input: User instruction.
            context: Layer 1 context.
            metadata: Additional metadata.

        Returns:
            Response dictionary.
        """
        query = user_input.lower().strip()

        # Security boundary check: Reject send attempts
        if "send email" in query or "send mail" in query or "send an email" in query:
            logger.warning("gmail_send_blocked_by_policy")
            return {
                "content": (
                    "Security Policy Restriction: Direct email sending is disabled by default. "
                    "I only have Gmail read access unless draft creation is explicitly enabled."
                ),
                "success": False,
                "source_agent": "email",
            }

        # Handle Draft Requests
        if "draft" in query or "reply" in query or "compose" in query:
            if not self._draft_creation_enabled():
                logger.warning("gmail_draft_blocked_by_policy")
                return {
                    "content": (
                        "Security Policy Restriction: Gmail draft creation is disabled by "
                        "default. Enable email.allow_draft_creation before requesting draft "
                        "creation."
                    ),
                    "success": False,
                    "source_agent": "email",
                }

            service = self._get_gmail_service(scopes=self._get_gmail_scopes(include_compose=True))

            # Simple parse helpers for testing / direct queries
            to = "recipient@example.com"
            if "to " in query:
                parts = query.split("to ")
                if len(parts) > 1:
                    to = parts[1].split()[0].strip()

            subject = "Draft Response"
            if "subject " in query:
                subj_parts = query.split("subject ")
                if len(subj_parts) > 1:
                    subject = subj_parts[1].split("body")[0].strip()

            body = "This is a draft email message created by Renine."
            if "body " in query:
                body_parts = query.split("body ")
                if len(body_parts) > 1:
                    body = body_parts[1].strip()

            res = self._create_draft(service, to, subject, body)
            if res["success"]:
                return {
                    "content": res["message"],
                    "success": True,
                    "source_agent": "email",
                    "draft_id": res.get("draft_id"),
                }
            else:
                return {
                    "content": f"Failed to create draft: {res.get('error')}",
                    "success": False,
                    "source_agent": "email",
                }

        # Default: List messages / Read inbox
        service = self._get_gmail_service()
        messages = self._list_messages(service)
        if not messages:
            return {
                "content": "No messages found in your inbox or unable to retrieve emails.",
                "success": True,
                "source_agent": "email",
            }

        msg_list_str = "\n".join(
            f"- **From**: {m['from']}\n  **Subject**: {m['subject']}\n  **Date**: {m['date']}"
            for m in messages
        )
        content = f"Here are your most recent emails:\n\n{msg_list_str}"

        return {
            "content": content,
            "success": True,
            "source_agent": "email",
            "messages": messages,
        }
