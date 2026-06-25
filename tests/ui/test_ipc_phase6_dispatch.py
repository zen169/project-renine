"""Tests for Phase 6 Electron IPC dispatch wiring."""
from __future__ import annotations

from pathlib import Path


IPC_HANDLERS = (
    Path(__file__).resolve().parents[2]
    / "renine"
    / "ui"
    / "electron"
    / "ipc_handlers.ts"
)


def _ipc_source() -> str:
    """Return the IPC handler source text."""
    return IPC_HANDLERS.read_text(encoding="utf-8")


def test_ipc_imports_phase6_agents() -> None:
    """Electron IPC Python bridge imports Phase 6 agents."""
    source = _ipc_source()

    assert "from renine.agents.browser_agent import BrowserAgent" in source
    assert "from renine.agents.email_agent import EmailAgent" in source
    assert "from renine.agents.news_agent import NewsAgent" in source


def test_ipc_dispatches_phase6_route_targets() -> None:
    """Electron IPC dispatches Browser, Email, and News route targets."""
    source = _ipc_source()

    assert "elif decision.target == RouteTarget.BROWSER_AGENT:" in source
    assert "    agent = BrowserAgent()" in source
    assert "elif decision.target == RouteTarget.EMAIL_AGENT:" in source
    assert "    agent = EmailAgent()" in source
    assert "elif decision.target == RouteTarget.NEWS_AGENT:" in source
    assert "    agent = NewsAgent()" in source


def test_ipc_status_reports_phase6() -> None:
    """Electron status endpoint reports the active Phase 6 version."""
    source = _ipc_source()

    assert "phase: 6" in source
    assert "version: '0.6.0'" in source
