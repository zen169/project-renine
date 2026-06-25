"""News agent for Renine.

Retrieves and summarizes news headlines from configured or user-supplied RSS feeds
using feedparser.
"""
from __future__ import annotations

from typing import Any

import feedparser

from renine.agents.base_agent import AgentManifest, BaseAgent, MemoryAccessLevel
from renine.brain import ollama_client
from renine.core.logging_config import get_logger
from renine.tools.permissions import PermissionLevel

logger = get_logger(__name__)

DEFAULT_FEEDS = {
    "tech": "https://techcrunch.com/feed/",
    "general": "http://feeds.bbci.co.uk/news/rss.xml",
}

_NEWS_SUMMARIZER_PROMPT = (
    "You are Renine, a helpful assistant. Below is a list of recent news headlines from an RSS feed. "
    "Provide a brief, organized summary of the key stories. Focus on readability and conciseness."
)


class NewsAgent(BaseAgent):
    """Agent that fetches news headlines from RSS feeds and displays them to the user."""

    def get_manifest(self) -> AgentManifest:
        """Return capability manifest for NewsAgent."""
        return AgentManifest(
            name="news",
            description="Retrieves latest news headlines from RSS feeds",
            required_tools=[],
            memory_access_level=MemoryAccessLevel.LAYER1_ONLY,
            permission_level=PermissionLevel.READ_ONLY,
            active_phase=6,
        )

    def _fetch_headlines(self, feed_url: str, limit: int = 5) -> list[dict[str, str]]:
        """Fetch headlines from a given RSS feed URL.

        Args:
            feed_url: The RSS URL.
            limit: Max headlines to return.

        Returns:
            List of dicts containing title, link, and summary.
        """
        logger.info("fetching_rss_feed", url=feed_url)
        try:
            feed = feedparser.parse(feed_url)
            
            # Check for parsing errors
            if feed.bozo and not feed.entries:
                logger.error("rss_parse_error", url=feed_url, exception=str(feed.bozo_exception))
                return []

            entries = feed.entries[:limit]
            headlines = []
            for entry in entries:
                headlines.append({
                    "title": entry.get("title", "(No Title)"),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", ""),
                    "published": entry.get("published", ""),
                })
            return headlines
        except Exception as e:
            logger.exception("failed_to_fetch_rss", url=feed_url)
            return []

    def process(
        self,
        user_input: str,
        context: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process news requests: fetch headlines from selected feed and summarize.

        Args:
            user_input: The user request (e.g. "show tech news" or custom URL).
            context: Layer 1 context.
            metadata: Additional metadata.

        Returns:
            Processing result dictionary.
        """
        query = user_input.lower().strip()
        feed_url = DEFAULT_FEEDS["general"]  # Default to general news

        # Select feed based on keywords
        if "tech" in query:
            feed_url = DEFAULT_FEEDS["tech"]
        elif "http" in query:
            # Extract custom URL from query
            for word in user_input.split():
                if word.startswith(("http://", "https://")):
                    feed_url = word.strip(".,'\"")
                    break

        headlines = self._fetch_headlines(feed_url)
        if not headlines:
            return {
                "content": f"Unable to retrieve headlines from feed: {feed_url}",
                "success": False,
                "source_agent": "news",
            }

        # Format headlines as text
        headlines_str = "\n".join(
            f"- **{h['title']}**\n  Published: {h['published']}\n  Link: {h['link']}"
            for h in headlines
        )

        # Summarize using local Ollama if available
        content_summary = ""
        if ollama_client.check_connection():
            prompt = f"RSS Feed URL: {feed_url}\nHeadlines:\n{headlines_str}"
            try:
                messages = [{"role": "user", "content": prompt}]
                content_summary = ollama_client.chat(messages=messages, system_prompt=_NEWS_SUMMARIZER_PROMPT)
            except Exception as e:
                logger.warning("news_summarization_failed", error=str(e))
                content_summary = f"Here are the latest headlines:\n\n{headlines_str}"
        else:
            content_summary = f"Here are the latest headlines:\n\n{headlines_str}"

        return {
            "content": content_summary,
            "success": True,
            "source_agent": "news",
            "headlines": headlines,
        }
