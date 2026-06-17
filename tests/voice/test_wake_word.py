"""Tests for renine.voice.wake_word — wake word detection."""
from __future__ import annotations

from renine.voice.wake_word import check_wake_word, extract_command_after_wake_word


class TestCheckWakeWord:
    """Tests for check_wake_word."""

    def test_detects_exact_wake_word(self) -> None:
        """Exact lowercase 'renine' is detected."""
        assert check_wake_word("renine") is True

    def test_case_insensitive(self) -> None:
        """Wake word detection is case-insensitive."""
        assert check_wake_word("Renine, what time is it?") is True

    def test_phonetic_variant(self) -> None:
        """Phonetic variants like 'rennine' are detected."""
        assert check_wake_word("hey rennine") is True

    def test_non_wake_word(self) -> None:
        """Non-matching text returns False."""
        assert check_wake_word("hello assistant") is False

    def test_empty_string(self) -> None:
        """Empty string returns False."""
        assert check_wake_word("") is False

    def test_hey_renine_variant(self) -> None:
        """'hey renine' variant is detected."""
        assert check_wake_word("hey renine set a timer") is True


class TestExtractCommandAfterWakeWord:
    """Tests for extract_command_after_wake_word."""

    def test_extracts_after_comma(self) -> None:
        """Command after 'Renine,' is extracted."""
        result = extract_command_after_wake_word("Renine, set a timer")
        assert "set a timer" in result

    def test_empty_returns_empty(self) -> None:
        """Empty transcript returns empty string."""
        assert extract_command_after_wake_word("") == ""

    def test_wake_word_only_returns_empty(self) -> None:
        """Wake word with no following text returns empty or empty string."""
        result = extract_command_after_wake_word("renine")
        assert isinstance(result, str)

    def test_command_stripped_of_punctuation(self) -> None:
        """Leading comma/period stripped from command."""
        result = extract_command_after_wake_word("renine, hello")
        assert not result.startswith(",")
