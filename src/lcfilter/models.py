"""Data models for logcatignore."""

from dataclasses import dataclass, field
from enum import Enum
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


# --- Scope Configuration ---

@dataclass
class AppScope:
    """Application scope information."""
    package: str = ""
    processes: list[str] = field(default_factory=list)


@dataclass
class ExpectedTags:
    """Tags expected from the app or its dependencies."""
    tags: list[str] = field(default_factory=list)


@dataclass
class ExpectedLibs:
    """Library prefixes expected in stack traces."""
    libs: list[str] = field(default_factory=list)


@dataclass
class StacktraceRoots:
    """Root packages for stack trace filtering."""
    roots: list[str] = field(default_factory=list)


@dataclass
class ScopeConfig:
    """Parsed .logcatscope configuration.

    This defines what is "in scope" for the current project.
    Useful for filtering, anomaly detection, and identifying
    relevant log entries.
    """
    app: AppScope = field(default_factory=AppScope)
    expected_tags: ExpectedTags = field(default_factory=ExpectedTags)
    expected_libs: ExpectedLibs = field(default_factory=ExpectedLibs)
    stacktrace_roots: StacktraceRoots = field(default_factory=StacktraceRoots)

    def is_tag_in_scope(self, tag: str) -> bool:
        """Check if a tag is in the expected tags list."""
        return tag in self.expected_tags.tags

    def is_process_in_scope(self, process: str) -> bool:
        """Check if a process name matches the app's processes."""
        return process in self.app.processes or process == self.app.package

    def is_stacktrace_in_scope(self, class_name: str) -> bool:
        """Check if a class name matches any stacktrace root."""
        return any(class_name.startswith(root) for root in self.stacktrace_roots.roots)


# --- Filter Result (for extensibility) ---

@dataclass
class FilterResult:
    """Result of filtering a log entry.

    This structure supports future extensions like anomaly scoring,
    categorization, and routing to different output streams.
    """
    entry: LogEntry
    should_display: bool
    matched_rule: IgnoreRule | None = None
    # Future fields for extensibility:
    # anomaly_score: float = 0.0
    # category: str | None = None
    # severity_override: LogLevel | None = None
