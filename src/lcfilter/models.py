"""Data models for lcfilter."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Pattern
import re


class LogLevel(Enum):
    """Android logcat log levels."""
    VERBOSE = "V"
    DEBUG = "D"
    INFO = "I"
    WARNING = "W"
    ERROR = "E"
    FATAL = "F"
    SILENT = "S"

    @classmethod
    def from_str(cls, value: str) -> "LogLevel":
        """Parse a log level from a string."""
        value = value.upper().strip()
        for level in cls:
            if level.value == value:
                return level
        raise ValueError(f"Unknown log level: {value}")


@dataclass(frozen=True)
class LogEntry:
    """A parsed logcat log entry.

    Attributes:
        raw_line: The original unparsed line.
        timestamp: The timestamp string (if present).
        pid: Process ID (if present).
        tid: Thread ID (if present).
        level: Log level (V, D, I, W, E, F, S).
        tag: The log tag.
        message: The log message content.
    """
    raw_line: str
    timestamp: str | None = None
    pid: int | None = None
    tid: int | None = None
    level: LogLevel | None = None
    tag: str | None = None
    message: str = ""


# --- Ignore Rule Types ---

class IgnoreRuleType(Enum):
    """Types of ignore rules supported in .logcatignore."""
    TAG = "TAG"
    LEVEL = "LEVEL"
    TAGLEVEL = "TAGLEVEL"
    PATTERN = "PATTERN"
    LINEPATTERN = "LINEPATTERN"


@dataclass(frozen=True)
class IgnoreRuleTag:
    """Ignore rule: match by tag name."""
    tag: str

    def matches(self, entry: LogEntry) -> bool:
        """Check if this rule matches the log entry."""
        return entry.tag == self.tag


@dataclass(frozen=True)
class IgnoreRuleLevel:
    """Ignore rule: match by log level."""
    level: LogLevel

    def matches(self, entry: LogEntry) -> bool:
        """Check if this rule matches the log entry."""
        return entry.level == self.level


@dataclass(frozen=True)
class IgnoreRuleTagLevel:
    """Ignore rule: match by tag AND level combination."""
    tag: str
    level: LogLevel

    def matches(self, entry: LogEntry) -> bool:
        """Check if this rule matches the log entry."""
        return entry.tag == self.tag and entry.level == self.level


@dataclass
class IgnoreRulePattern:
    """Ignore rule: match by regex pattern on the message."""
    pattern_str: str
    _compiled: Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._compiled = re.compile(self.pattern_str)

    def matches(self, entry: LogEntry) -> bool:
        """Check if this rule matches the log entry."""
        return bool(self._compiled.search(entry.message))


@dataclass
class IgnoreRuleLinePattern:
    """Ignore rule: match by regex pattern on the full raw line."""
    pattern_str: str
    _compiled: Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._compiled = re.compile(self.pattern_str)

    def matches(self, entry: LogEntry) -> bool:
        """Check if this rule matches the log entry."""
        return bool(self._compiled.search(entry.raw_line))


# Union type for all ignore rules
IgnoreRule = (
    IgnoreRuleTag
    | IgnoreRuleLevel
    | IgnoreRuleTagLevel
    | IgnoreRulePattern
    | IgnoreRuleLinePattern
)


@dataclass
class IgnoreConfig:
    """Parsed .logcatignore configuration."""
    rules: list[IgnoreRule] = field(default_factory=list)

    def add_rule(self, rule: IgnoreRule) -> None:
        """Add an ignore rule."""
        self.rules.append(rule)


# --- Scope Configuration (simplified) ---

@dataclass
class ScopeConfig:
    """Parsed .logcatscope configuration.

    Contains a set of tags that are considered "in scope" for your app.
    In-scope logs are routed to the InScope output stream.
    """
    tags: set[str] = field(default_factory=set)

    def is_tag_in_scope(self, tag: str) -> bool:
        """Check if a tag is in scope."""
        return tag in self.tags


# --- Routing ---

class RouteCategory(Enum):
    """Categories for three-stream output routing.

    IN_SCOPE: Tag is in .logcatscope (your app's logs)
    IGNORED: Matches a rule in .logcatignore (known noise)
    NOISE: Everything else (unknown - refine over time)
    """
    IN_SCOPE = auto()
    IGNORED = auto()
    NOISE = auto()


@dataclass
class RouteResult:
    """Result of routing a log entry to an output stream."""
    entry: LogEntry
    category: RouteCategory
    matched_rule: IgnoreRule | None = None


# --- Filter Result (for backward compatibility) ---

@dataclass
class FilterResult:
    """Result of filtering a log entry.

    This structure supports future extensions like anomaly scoring,
    categorization, and routing to different output streams.
    """
    entry: LogEntry
    should_display: bool
    matched_rule: IgnoreRule | None = None
