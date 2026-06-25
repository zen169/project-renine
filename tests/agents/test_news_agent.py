"""Tests for renine.agents.news_agent — News Agent.

Validates:
- Fetching headlines from default feeds.
- Supporting custom RSS feeds.
- Correct feed parsing and text formatting.
- Summarization falls back properly when Ollama is offline.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from renine.agents.news_agent import NewsAgent


class TestNewsAgent:
    """Tests for the NewsAgent implementation."""

    @patch("renine.agents.news_agent.feedparser.parse")
    @patch("renine.agents.news_agent.ollama_client")
    def test_fetch_default_headlines_without_ollama(
        self, mock_ollama: MagicMock, mock_parse: MagicMock
    ) -> None:
        """NewsAgent successfully parses RSS feed and lists entries when Ollama is offline."""
        mock_ollama.check_connection.return_value = False
        
        # Mock FeedParser output
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda key, default="": {
            "title": "Renine Phase 6 Released",
            "link": "https://renine.local/news/1",
            "summary": "This is a summary of the phase release.",
            "published": "Thu, 18 Jun 2026",
        }.get(key, default)
        
        mock_feed.entries = [mock_entry]
        mock_parse.return_value = mock_feed

        agent = NewsAgent()
        result = agent.process("show general news")

        assert result["success"] is True
        assert result["source_agent"] == "news"
        assert "Renine Phase 6 Released" in result["content"]
        assert "https://renine.local/news/1" in result["content"]
        mock_parse.assert_called_with("http://feeds.bbci.co.uk/news/rss.xml")

    @patch("renine.agents.news_agent.feedparser.parse")
    @patch("renine.agents.news_agent.ollama_client")
    def test_fetch_custom_feed_url(
        self, mock_ollama: MagicMock, mock_parse: MagicMock
    ) -> None:
        """NewsAgent correctly extracts and fetches custom HTTP RSS feed URLs."""
        mock_ollama.check_connection.return_value = False
        
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        agent = NewsAgent()
        # Custom RSS URL in the request
        agent.process("fetch news from https://mycustomfeed.org/rss.xml")

        mock_parse.assert_called_with("https://mycustomfeed.org/rss.xml")

    @patch("renine.agents.news_agent.feedparser.parse")
    @patch("renine.agents.news_agent.ollama_client")
    def test_summarization_with_ollama(
        self, mock_ollama: MagicMock, mock_parse: MagicMock
    ) -> None:
        """If Ollama is online, feed items are sent to the LLM for summarization."""
        mock_ollama.check_connection.return_value = True
        mock_ollama.chat.return_value = "This is a nice aggregated summary."

        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [MagicMock()]
        mock_parse.return_value = mock_feed

        agent = NewsAgent()
        result = agent.process("show tech news")

        assert result["success"] is True
        assert result["content"] == "This is a nice aggregated summary."
        mock_ollama.chat.assert_called_once()
        mock_parse.assert_called_with("https://techcrunch.com/feed/")
