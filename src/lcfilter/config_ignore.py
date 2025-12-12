"""Parser for .logcatignore configuration files."""

from pathlib import Path
import re

from .models import (
    IgnoreConfig,
    IgnoreRule,
    IgnoreRuleTag,
    IgnoreRuleLevel,
    IgnoreRuleTagLevel,
    IgnoreRulePattern,
    IgnoreRuleLinePattern,
    LogLevel,
)


class IgnoreParseError(Exception):
    """Error parsing .logcatignore file."""

    def __init__(self, message: str, line_number: int, line_content: str):
        self.line_number = line_number
        self.line_content = line_content
        super().__init__(f"Line {line_number}: {message}\n  Content: {line_content!r}")


def parse_ignore_file(path: Path) -> IgnoreConfig:
    """Parse a .logcatignore file from disk.

    Args:
        path: Path to the .logcatignore file.

    Returns:
        Parsed IgnoreConfig with all rules.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        IgnoreParseError: If the file contains invalid syntax.
    """
    content = path.read_text(encoding="utf-8")
    return parse_ignore_content(content)


def parse_ignore_content(content: str) -> IgnoreConfig:
    """Parse .logcatignore content from a string.

    Args:
        content: The raw content of a .logcatignore file.

    Returns:
        Parsed IgnoreConfig with all rules.

    Raises:
        IgnoreParseError: If the content contains invalid syntax.
    """
    config = IgnoreConfig()

    for line_number, line in enumerate(content.splitlines(), start=1):
        rule = parse_ignore_line(line, line_number)
        if rule is not None:
            config.add_rule(rule)

    return config


def parse_ignore_line(line: str, line_number: int) -> IgnoreRule | None:
    """Parse a single line from a .logcatignore file.

    Args:
        line: The line content.
        line_number: Line number for error reporting.

    Returns:
        An IgnoreRule if the line contains a rule, None if comment/blank.

    Raises:
        IgnoreParseError: If the line contains invalid syntax.
    """
    # Strip whitespace
    line = line.strip()

    # Skip empty lines and comments
    if not line or line.startswith("#"):
        return None

    # Parse rule type and value
    if ":" not in line:
        raise IgnoreParseError(
            "Invalid rule format. Expected TYPE:value",
            line_number,
            line,
        )

    # Split only on first colon for PREFIX:value format
    rule_type, _, value = line.partition(":")
    rule_type = rule_type.strip().upper()
    value = value.strip()

    if not value:
        raise IgnoreParseError(
            f"Empty value for rule type {rule_type}",
            line_number,
            line,
        )

    match rule_type:
        case "TAG":
            return _parse_tag_rule(value, line_number, line)
        case "LEVEL":
            return _parse_level_rule(value, line_number, line)
        case "TAGLEVEL":
            return _parse_taglevel_rule(value, line_number, line)
        case "PATTERN":
            return _parse_pattern_rule(value, line_number, line)
        case "LINEPATTERN":
            return _parse_linepattern_rule(value, line_number, line)
        case _:
            raise IgnoreParseError(
                f"Unknown rule type: {rule_type}. "
                "Expected TAG, LEVEL, TAGLEVEL, PATTERN, or LINEPATTERN",
                line_number,
                line,
            )


def _parse_tag_rule(value: str, line_number: int, line: str) -> IgnoreRuleTag:
    """Parse a TAG:SomeTag rule."""
    if not value:
        raise IgnoreParseError("TAG rule requires a tag name", line_number, line)
    return IgnoreRuleTag(tag=value)


def _parse_level_rule(value: str, line_number: int, line: str) -> IgnoreRuleLevel:
    """Parse a LEVEL:V rule."""
    try:
        level = LogLevel.from_str(value)
    except ValueError as e:
        raise IgnoreParseError(str(e), line_number, line) from e
    return IgnoreRuleLevel(level=level)


def _parse_taglevel_rule(value: str, line_number: int, line: str) -> IgnoreRuleTagLevel:
    """Parse a TAGLEVEL:SomeTag:W rule."""
    parts = value.split(":")
    if len(parts) != 2:
        raise IgnoreParseError(
            "TAGLEVEL rule requires format TAGLEVEL:TagName:Level",
            line_number,
            line,
        )

    tag = parts[0].strip()
    level_str = parts[1].strip()

    if not tag:
        raise IgnoreParseError("TAGLEVEL rule requires a tag name", line_number, line)

    try:
        level = LogLevel.from_str(level_str)
    except ValueError as e:
        raise IgnoreParseError(str(e), line_number, line) from e

    return IgnoreRuleTagLevel(tag=tag, level=level)


def _parse_pattern_rule(value: str, line_number: int, line: str) -> IgnoreRulePattern:
    """Parse a PATTERN:regex rule."""
    try:
        # Validate the regex by compiling it
        re.compile(value)
    except re.error as e:
        raise IgnoreParseError(f"Invalid regex pattern: {e}", line_number, line) from e

    return IgnoreRulePattern(pattern_str=value)


def _parse_linepattern_rule(value: str, line_number: int, line: str) -> IgnoreRuleLinePattern:
    """Parse a LINEPATTERN:regex rule."""
    try:
        # Validate the regex by compiling it
        re.compile(value)
    except re.error as e:
        raise IgnoreParseError(f"Invalid regex pattern: {e}", line_number, line) from e

    return IgnoreRuleLinePattern(pattern_str=value)


# --- Sample file generation ---

SAMPLE_LOGCATIGNORE = """\
# .logcatignore - Define patterns to hide from logcat output
#
# Supported rule types:
#   TAG:TagName           - Ignore all lines with this tag
#   LEVEL:V               - Ignore all lines with this level (V/D/I/W/E)
#   TAGLEVEL:TagName:V    - Ignore lines with this tag AND level
#   PATTERN:regex         - Ignore lines where message matches regex
#   LINEPATTERN:regex     - Ignore lines where full line matches regex

# Ignore verbose and debug logs by default
LEVEL:V
LEVEL:D

# Common noisy system tags
TAG:chatty
TAG:ViewRootImpl
TAG:InputMethodManager
TAG:HwRemoteInputMethodManager

# Ignore GC messages
PATTERN:^(Concurrent|Background|Explicit) (young|partial|sticky|full) (GC|concurrent)

# Ignore common framework noise
TAG:ActivityThread
TAGLEVEL:ActivityManager:I

# Ignore art/dalvik memory stats
LINEPATTERN:.*\\bART\\b.*\\b(GC|alloc|free)\\b.*
"""


def generate_sample_ignore_file(path: Path) -> bool:
    """Generate a sample .logcatignore file.

    Args:
        path: Path where the file should be created.

    Returns:
        True if file was created, False if it already exists.
    """
    if path.exists():
        return False

    path.write_text(SAMPLE_LOGCATIGNORE, encoding="utf-8")
    return True
