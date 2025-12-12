"""Parser for Android logcat output lines."""

import re
from typing import Iterator

from .models import LogEntry, LogLevel


# Common logcat formats:
#
# 1. threadtime (default): "MM-DD HH:MM:SS.mmm  PID  TID LEVEL TAG: message"
#    Example: "12-25 13:45:23.456  1234  5678 D MyTag  : Hello world"
#
# 2. brief: "LEVEL/TAG(PID): message"
#    Example: "D/MyTag( 1234): Hello world"
#
# 3. process: "LEVEL(PID) message"
#    Example: "D( 1234) Hello world"
#
# 4. tag: "LEVEL/TAG: message"
#    Example: "D/MyTag: Hello world"
#
# 5. time: "MM-DD HH:MM:SS.mmm LEVEL/TAG(PID): message"
#    Example: "12-25 13:45:23.456 D/MyTag( 1234): Hello world"

# Regex for threadtime format (most common/default)
# Format: "MM-DD HH:MM:SS.mmm  PID  TID LEVEL TAG: message"
THREADTIME_PATTERN = re.compile(
    r"^(?P<timestamp>\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+"
    r"(?P<pid>\d+)\s+"
    r"(?P<tid>\d+)\s+"
    r"(?P<level>[VDIWEFS])\s+"
    r"(?P<tag>\S+)\s*:\s*"
    r"(?P<message>.*)$"
)

# Regex for brief format: "LEVEL/TAG(PID): message"
BRIEF_PATTERN = re.compile(
    r"^(?P<level>[VDIWEFS])/(?P<tag>[^(]+)\(\s*(?P<pid>\d+)\):\s*(?P<message>.*)$"
)

# Regex for tag format: "LEVEL/TAG: message"
TAG_PATTERN = re.compile(
    r"^(?P<level>[VDIWEFS])/(?P<tag>[^:]+):\s*(?P<message>.*)$"
)

# Regex for time format: "MM-DD HH:MM:SS.mmm LEVEL/TAG(PID): message"
TIME_PATTERN = re.compile(
    r"^(?P<timestamp>\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+"
    r"(?P<level>[VDIWEFS])/(?P<tag>[^(]+)\(\s*(?P<pid>\d+)\):\s*"
    r"(?P<message>.*)$"
)

# Regex for process format: "LEVEL(PID) message"
PROCESS_PATTERN = re.compile(
    r"^(?P<level>[VDIWEFS])\(\s*(?P<pid>\d+)\)\s*(?P<message>.*)$"
)

# List of patterns to try in order (most specific first)
PATTERNS = [
    THREADTIME_PATTERN,
    TIME_PATTERN,
    BRIEF_PATTERN,
    TAG_PATTERN,
    PROCESS_PATTERN,
]


def parse_logcat_line(line: str) -> LogEntry:
    """Parse a single logcat line into a LogEntry.

    Attempts to match against known logcat formats. If no format matches,
    returns a LogEntry with only the raw_line set.

    Args:
        line: A single line from logcat output.

    Returns:
        A LogEntry with parsed fields, or just raw_line if unparseable.
    """
    line = line.rstrip("\n\r")

    for pattern in PATTERNS:
        match = pattern.match(line)
        if match:
            return _build_entry_from_match(line, match)

    # No pattern matched - return entry with just raw line
    return LogEntry(raw_line=line)


def _build_entry_from_match(raw_line: str, match: re.Match[str]) -> LogEntry:
    """Build a LogEntry from a regex match."""
    groups = match.groupdict()

    # Parse level
    level = None
    if "level" in groups:
        try:
            level = LogLevel.from_str(groups["level"])
        except ValueError:
            pass

    # Parse PID
    pid = None
    if "pid" in groups and groups["pid"]:
        try:
            pid = int(groups["pid"])
        except ValueError:
            pass

    # Parse TID
    tid = None
    if "tid" in groups and groups["tid"]:
        try:
            tid = int(groups["tid"])
        except ValueError:
            pass

    return LogEntry(
        raw_line=raw_line,
        timestamp=groups.get("timestamp"),
        pid=pid,
        tid=tid,
        level=level,
        tag=groups.get("tag", "").strip() if groups.get("tag") else None,
        message=groups.get("message", ""),
    )


def parse_logcat_lines(lines: Iterator[str]) -> Iterator[LogEntry]:
    """Parse multiple logcat lines.

    Args:
        lines: Iterator of logcat lines.

    Yields:
        LogEntry for each parsed line.
    """
    for line in lines:
        yield parse_logcat_line(line)


def parse_logcat_text(text: str) -> list[LogEntry]:
    """Parse logcat text containing multiple lines.

    Args:
        text: Multi-line logcat output.

    Returns:
        List of LogEntry objects.
    """
    return list(parse_logcat_lines(iter(text.splitlines())))


class LogcatStreamParser:
    """Streaming parser for logcat output.

    This class provides a stateful parser that can handle partial lines
    and multi-line log entries (like stack traces) in the future.

    Currently handles line-by-line parsing, but designed for extension.
    """

    def __init__(self) -> None:
        self._buffer: str = ""

    def feed(self, data: str) -> Iterator[LogEntry]:
        """Feed data to the parser and yield complete entries.

        Args:
            data: Raw data from logcat output.

        Yields:
            LogEntry for each complete line.
        """
        self._buffer += data

        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line:  # Skip empty lines from split
                yield parse_logcat_line(line)

    def flush(self) -> LogEntry | None:
        """Flush any remaining buffered data.

        Returns:
            Final LogEntry if there's buffered data, None otherwise.
        """
        if self._buffer.strip():
            entry = parse_logcat_line(self._buffer)
            self._buffer = ""
            return entry
        self._buffer = ""
        return None
