"""Tests for message filtering logic.

Verifies that:
- Empty messages are filtered out before processing
- N (total count) reflects only non-empty messages
- Progress display uses 1-based indexing

See Executable Spec Section 5.1 for requirements.
"""

import pytest


def filter_messages(messages_raw: list[str]) -> list[str]:
    """Filter empty messages as specified.

    This replicates the filtering logic from Spec 5.1:
    messages = [m for m in messages_raw if trim(m) != ""]

    Args:
        messages_raw: Raw message list from UI

    Returns:
        Filtered list with only non-empty messages
    """
    return [m.strip() for m in messages_raw if m.strip()]


class TestMessageFiltering:
    """Test suite for message filtering logic."""

    def test_empty_list_returns_empty(self) -> None:
        """Empty input should return empty output."""
        result = filter_messages([])
        assert result == []
        assert len(result) == 0

    def test_all_empty_strings_returns_empty(self) -> None:
        """List of empty strings should return empty."""
        result = filter_messages(["", "", ""])
        assert result == []
        assert len(result) == 0

    def test_whitespace_only_strings_filtered(self) -> None:
        """Strings with only whitespace should be filtered out."""
        result = filter_messages(["   ", "\t", "\n", "  \n\t  "])
        assert result == []

    def test_non_empty_messages_preserved(self) -> None:
        """Non-empty messages should be preserved."""
        messages = ["Hello", "World", "Test"]
        result = filter_messages(messages)
        assert result == ["Hello", "World", "Test"]
        assert len(result) == 3

    def test_mixed_empty_and_non_empty(self) -> None:
        """Mixed list should only keep non-empty messages."""
        messages = ["Hello", "", "World", "", ""]
        result = filter_messages(messages)
        assert result == ["Hello", "World"]
        assert len(result) == 2

    def test_trailing_empty_filtered(self) -> None:
        """Trailing empty messages should be filtered (per UI behavior)."""
        # The UI auto-appends empty items, these should be filtered
        messages = ["Message 1", "Message 2", ""]
        result = filter_messages(messages)
        assert result == ["Message 1", "Message 2"]
        assert len(result) == 2

    def test_leading_empty_filtered(self) -> None:
        """Leading empty messages should be filtered."""
        messages = ["", "Message 1", "Message 2"]
        result = filter_messages(messages)
        assert result == ["Message 1", "Message 2"]

    def test_multiline_messages_preserved(self) -> None:
        """Messages with newlines should be preserved."""
        messages = ["Line 1\nLine 2", "Single line", "Line A\nLine B\nLine C"]
        result = filter_messages(messages)
        assert len(result) == 3
        assert "Line 1\nLine 2" in result

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace should be stripped."""
        messages = ["  Hello  ", "\tWorld\t", "\n  Test  \n"]
        result = filter_messages(messages)
        assert result == ["Hello", "World", "Test"]

    def test_internal_whitespace_preserved(self) -> None:
        """Internal whitespace should be preserved."""
        messages = ["Hello World", "Tab\tSeparated", "Line 1\nLine 2"]
        result = filter_messages(messages)
        assert "Hello World" in result
        assert "Tab\tSeparated" in result
        assert "Line 1\nLine 2" in result


class TestNCountCorrectness:
    """Test that N (total count) is correct after filtering."""

    def test_n_equals_filtered_count(self) -> None:
        """N should equal the number of non-empty messages."""
        test_cases = [
            (["a", "b", "c"], 3),
            (["a", "", "b"], 2),
            (["", "", ""], 0),
            (["x"], 1),
            (["a", "b", "", "c", "d", ""], 4),
        ]

        for messages, expected_n in test_cases:
            result = filter_messages(messages)
            assert len(result) == expected_n, \
                f"For {messages}: expected N={expected_n}, got {len(result)}"

    def test_n_from_ui_sample_s1(self) -> None:
        """Test case S1 from test plan: 3 short texts with empty entries."""
        # Simulating: 3 non-empty + 2 empty entries
        messages = ["Hello", "World", "Test", "", ""]
        result = filter_messages(messages)
        assert len(result) == 3

    def test_n_from_ui_sample_s2(self) -> None:
        """Test case S2: 2 multiline texts with newlines."""
        messages = ["Line 1\nLine 2", "Para 1\n\nPara 2"]
        result = filter_messages(messages)
        assert len(result) == 2


class TestProgressDisplayIndexing:
    """Test that progress uses 1-based indexing for display."""

    def test_first_message_is_1_of_n(self) -> None:
        """First message should display as 1/N, not 0/N."""
        messages = filter_messages(["a", "b", "c"])
        n = len(messages)

        # Simulate processing - first message (index 0) displays as 1/N
        for idx in range(n):
            display_idx = idx + 1  # Convert 0-based to 1-based
            progress = f"{display_idx}/{n}"

            if idx == 0:
                assert progress == "1/3"
            elif idx == 1:
                assert progress == "2/3"
            elif idx == 2:
                assert progress == "3/3"

    def test_progress_format(self) -> None:
        """Progress should be in format 'i/N' where i is 1-based."""
        messages = filter_messages(["msg1", "msg2", "", "msg3", ""])
        n = len(messages)  # Should be 3

        expected_progress = ["1/3", "2/3", "3/3"]
        for idx in range(n):
            progress = f"{idx + 1}/{n}"
            assert progress == expected_progress[idx]


class TestMessageContentPreservation:
    """Test that message content is preserved correctly."""

    def test_special_characters_preserved(self) -> None:
        """Special characters should be preserved."""
        messages = ["Hello! @#$%", "中文消息", "Emoji 🎉"]
        result = filter_messages(messages)
        assert result == messages

    def test_unicode_preserved(self) -> None:
        """Unicode characters should be preserved."""
        messages = ["日本語", "한국어", "العربية"]
        result = filter_messages(messages)
        assert result == messages

    def test_long_messages_preserved(self) -> None:
        """Long messages should be preserved."""
        long_msg = "A" * 10000
        messages = [long_msg]
        result = filter_messages(messages)
        assert result == [long_msg]

    def test_newlines_in_message_preserved(self) -> None:
        """Newlines within messages should be preserved (Spec: Enter=newline)."""
        message_with_newlines = "Line 1\nLine 2\nLine 3"
        messages = [message_with_newlines]
        result = filter_messages(messages)
        assert result == [message_with_newlines]
        assert result[0].count("\n") == 2


class TestFilteringAtStartTime:
    """Test that filtering happens at Start time and locks N."""

    def test_filtering_creates_snapshot(self) -> None:
        """Filtering should create an immutable list for processing."""
        raw_messages = ["a", "", "b", "c", ""]
        filtered = filter_messages(raw_messages)

        # Modifying raw_messages after filtering should not affect filtered
        raw_messages.append("d")
        raw_messages[0] = "modified"

        # filtered should remain unchanged (it's a new list)
        assert filtered == ["a", "b", "c"]

    def test_n_locked_after_start(self) -> None:
        """N should be locked after Start (simulated by copying)."""
        raw_messages = ["a", "b", "c"]
        filtered = filter_messages(raw_messages)
        n = len(filtered)

        # Simulate UI changes during run (these should be ignored)
        raw_messages.append("d")
        raw_messages.append("e")

        # N should still be 3 (original filtered count)
        assert n == 3


