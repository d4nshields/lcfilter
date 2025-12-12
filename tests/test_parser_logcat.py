"""Tests for logcat line parsing."""

import pytest

from lcfilter.parser_logcat import (
    parse_logcat_line,
    parse_logcat_text,
    LogcatStreamParser,
)
from lcfilter.models import LogLevel


class TestParseLogcatLine:
    """Tests for parse_logcat_line function."""

    def test_threadtime_format(self):
        """Should parse threadtime format (default logcat format)."""
        line = "12-25 13:45:23.456  1234  5678 D MyTag   : Hello world"
        entry = parse_logcat_line(line)

        assert entry.raw_line == line
        assert entry.timestamp == "12-25 13:45:23.456"
        assert entry.pid == 1234
        assert entry.tid == 5678
        assert entry.level == LogLevel.DEBUG
        assert entry.tag == "MyTag"
        assert entry.message == "Hello world"

    def test_threadtime_format_all_levels(self):
        """Should parse all log levels in threadtime format."""
        levels = [
            ("V", LogLevel.VERBOSE),
            ("D", LogLevel.DEBUG),
            ("I", LogLevel.INFO),
            ("W", LogLevel.WARNING),
            ("E", LogLevel.ERROR),
            ("F", LogLevel.FATAL),
        ]

        for level_char, level_enum in levels:
            line = f"01-01 00:00:00.000  1000  1000 {level_char} Tag     : msg"
            entry = parse_logcat_line(line)
            assert entry.level == level_enum, f"Failed for level {level_char}"

    def test_brief_format(self):
        """Should parse brief format: D/Tag(PID): message."""
        line = "D/MyTag( 1234): Hello world"
        entry = parse_logcat_line(line)

        assert entry.raw_line == line
        assert entry.level == LogLevel.DEBUG
        assert entry.tag == "MyTag"
        assert entry.pid == 1234
        assert entry.message == "Hello world"

    def test_brief_format_padded_pid(self):
        """Should handle padded PID in brief format."""
        line = "I/ActivityManager(  123): Process started"
        entry = parse_logcat_line(line)

        assert entry.level == LogLevel.INFO
        assert entry.tag == "ActivityManager"
        assert entry.pid == 123

    def test_tag_format(self):
        """Should parse tag format: D/Tag: message."""
        line = "W/MyTag: Warning message"
        entry = parse_logcat_line(line)

        assert entry.raw_line == line
        assert entry.level == LogLevel.WARNING
        assert entry.tag == "MyTag"
        assert entry.message == "Warning message"
        assert entry.pid is None

    def test_time_format(self):
        """Should parse time format: timestamp D/Tag(PID): message."""
        line = "12-25 13:45:23.456 E/CrashTag( 5678): Exception occurred"
        entry = parse_logcat_line(line)

        assert entry.timestamp == "12-25 13:45:23.456"
        assert entry.level == LogLevel.ERROR
        assert entry.tag == "CrashTag"
        assert entry.pid == 5678
        assert entry.message == "Exception occurred"

    def test_process_format(self):
        """Should parse process format: D(PID) message."""
        line = "I( 1234) Some info message"
        entry = parse_logcat_line(line)

        assert entry.level == LogLevel.INFO
        assert entry.pid == 1234
        assert entry.message == "Some info message"
        assert entry.tag is None

    def test_unparseable_line(self):
        """Unparseable lines should return entry with raw_line only."""
        line = "This is not a logcat line"
        entry = parse_logcat_line(line)

        assert entry.raw_line == line
        assert entry.level is None
        assert entry.tag is None
        assert entry.pid is None

    def test_empty_line(self):
        """Empty lines should return entry with empty raw_line."""
        entry = parse_logcat_line("")
        assert entry.raw_line == ""
        assert entry.level is None

    def test_message_with_colon(self):
        """Messages containing colons should be preserved."""
        line = "D/MyTag( 1234): Key: value: nested"
        entry = parse_logcat_line(line)
        assert entry.message == "Key: value: nested"

    def test_long_tag(self):
        """Should handle long tag names."""
        line = "D/VeryLongTagNameThatIsMoreThan23Characters( 1234): msg"
        entry = parse_logcat_line(line)
        assert "VeryLongTagName" in entry.tag

    def test_strips_newline(self):
        """Should strip trailing newlines."""
        line = "D/Tag( 1234): message\n"
        entry = parse_logcat_line(line)
        assert entry.raw_line == "D/Tag( 1234): message"
        assert entry.message == "message"


class TestParseLogcatText:
    """Tests for parse_logcat_text function."""

    def test_multiple_lines(self):
        """Should parse multiple lines."""
        text = """D/Tag1( 1234): Message 1
D/Tag2( 5678): Message 2
I/Tag3( 9999): Message 3"""

        entries = parse_logcat_text(text)

        assert len(entries) == 3
        assert entries[0].tag == "Tag1"
        assert entries[1].tag == "Tag2"
        assert entries[2].tag == "Tag3"

    def test_empty_text(self):
        """Empty text should return empty list."""
        entries = parse_logcat_text("")
        assert entries == []

    def test_mixed_formats(self):
        """Should handle mixed log formats."""
        text = """D/Brief( 1234): Brief format
12-25 00:00:00.000  1234  5678 I ThreadT : Threadtime format"""

        entries = parse_logcat_text(text)

        assert len(entries) == 2
        assert entries[0].tag == "Brief"
        assert entries[1].tag == "ThreadT"


class TestLogcatStreamParser:
    """Tests for LogcatStreamParser class."""

    def test_single_complete_line(self):
        """Should yield entry for complete line."""
        parser = LogcatStreamParser()
        entries = list(parser.feed("D/Tag( 1234): message\n"))

        assert len(entries) == 1
        assert entries[0].tag == "Tag"

    def test_multiple_lines_in_one_feed(self):
        """Should yield multiple entries for multiple lines."""
        parser = LogcatStreamParser()
        entries = list(parser.feed("D/Tag1( 1): msg1\nD/Tag2( 2): msg2\n"))

        assert len(entries) == 2
        assert entries[0].tag == "Tag1"
        assert entries[1].tag == "Tag2"

    def test_partial_line_buffering(self):
        """Should buffer partial lines."""
        parser = LogcatStreamParser()

        # First feed: partial line
        entries1 = list(parser.feed("D/Tag( 1234):"))
        assert len(entries1) == 0

        # Second feed: complete the line
        entries2 = list(parser.feed(" message\n"))
        assert len(entries2) == 1
        assert entries2[0].tag == "Tag"
        assert entries2[0].message == "message"

    def test_flush_remaining(self):
        """Flush should return any buffered content."""
        parser = LogcatStreamParser()

        # Feed partial line (no newline)
        list(parser.feed("D/Tag( 1234): partial"))

        # Flush should return it
        entry = parser.flush()
        assert entry is not None
        assert entry.tag == "Tag"

    def test_flush_empty(self):
        """Flush on empty buffer should return None."""
        parser = LogcatStreamParser()
        assert parser.flush() is None

    def test_incremental_feeding(self):
        """Should handle character-by-character feeding."""
        parser = LogcatStreamParser()
        line = "D/Tag( 1234): message\n"

        all_entries = []
        for char in line:
            all_entries.extend(parser.feed(char))

        assert len(all_entries) == 1
        assert all_entries[0].tag == "Tag"
