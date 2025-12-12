"""Parser for .logcatscope configuration files (TOML format)."""

from pathlib import Path
import tomllib
from typing import Any

from .models import (
    ScopeConfig,
    AppScope,
    ExpectedTags,
    ExpectedLibs,
    StacktraceRoots,
)


class ScopeParseError(Exception):
    """Error parsing .logcatscope file."""

    def __init__(self, message: str, key: str | None = None):
        self.key = key
        if key:
            super().__init__(f"Error at '{key}': {message}")
        else:
            super().__init__(message)


def parse_scope_file(path: Path) -> ScopeConfig:
    """Parse a .logcatscope file from disk.

    Args:
        path: Path to the .logcatscope file.

    Returns:
        Parsed ScopeConfig.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ScopeParseError: If the file contains invalid content.
    """
    content = path.read_text(encoding="utf-8")
    return parse_scope_content(content)


def parse_scope_content(content: str) -> ScopeConfig:
    """Parse .logcatscope content from a string.

    Args:
        content: The raw TOML content of a .logcatscope file.

    Returns:
        Parsed ScopeConfig.

    Raises:
        ScopeParseError: If the content is invalid.
    """
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError as e:
        raise ScopeParseError(f"Invalid TOML: {e}") from e

    return _build_scope_config(data)


def _build_scope_config(data: dict[str, Any]) -> ScopeConfig:
    """Build a ScopeConfig from parsed TOML data."""
    config = ScopeConfig()

    # Parse [app] section
    if "app" in data:
        config.app = _parse_app_section(data["app"])

    # Parse [expected_tags] section
    if "expected_tags" in data:
        config.expected_tags = _parse_expected_tags_section(data["expected_tags"])

    # Parse [expected_libs] section
    if "expected_libs" in data:
        config.expected_libs = _parse_expected_libs_section(data["expected_libs"])

    # Parse [stacktrace_roots] section
    if "stacktrace_roots" in data:
        config.stacktrace_roots = _parse_stacktrace_roots_section(data["stacktrace_roots"])

    return config


def _parse_app_section(data: Any) -> AppScope:
    """Parse the [app] section."""
    if not isinstance(data, dict):
        raise ScopeParseError("Expected a table/dict", key="app")

    app = AppScope()

    if "package" in data:
        if not isinstance(data["package"], str):
            raise ScopeParseError("Expected a string", key="app.package")
        app.package = data["package"]

    if "processes" in data:
        if not isinstance(data["processes"], list):
            raise ScopeParseError("Expected a list", key="app.processes")
        for i, item in enumerate(data["processes"]):
            if not isinstance(item, str):
                raise ScopeParseError(f"Expected string at index {i}", key="app.processes")
        app.processes = data["processes"]

    return app


def _parse_expected_tags_section(data: Any) -> ExpectedTags:
    """Parse the [expected_tags] section."""
    if not isinstance(data, dict):
        raise ScopeParseError("Expected a table/dict", key="expected_tags")

    tags = ExpectedTags()

    if "tags" in data:
        if not isinstance(data["tags"], list):
            raise ScopeParseError("Expected a list", key="expected_tags.tags")
        for i, item in enumerate(data["tags"]):
            if not isinstance(item, str):
                raise ScopeParseError(f"Expected string at index {i}", key="expected_tags.tags")
        tags.tags = data["tags"]

    return tags


def _parse_expected_libs_section(data: Any) -> ExpectedLibs:
    """Parse the [expected_libs] section."""
    if not isinstance(data, dict):
        raise ScopeParseError("Expected a table/dict", key="expected_libs")

    libs = ExpectedLibs()

    if "libs" in data:
        if not isinstance(data["libs"], list):
            raise ScopeParseError("Expected a list", key="expected_libs.libs")
        for i, item in enumerate(data["libs"]):
            if not isinstance(item, str):
                raise ScopeParseError(f"Expected string at index {i}", key="expected_libs.libs")
        libs.libs = data["libs"]

    return libs


def _parse_stacktrace_roots_section(data: Any) -> StacktraceRoots:
    """Parse the [stacktrace_roots] section."""
    if not isinstance(data, dict):
        raise ScopeParseError("Expected a table/dict", key="stacktrace_roots")

    roots = StacktraceRoots()

    if "roots" in data:
        if not isinstance(data["roots"], list):
            raise ScopeParseError("Expected a list", key="stacktrace_roots.roots")
        for i, item in enumerate(data["roots"]):
            if not isinstance(item, str):
                raise ScopeParseError(f"Expected string at index {i}", key="stacktrace_roots.roots")
        roots.roots = data["roots"]

    return roots


# --- Sample file generation ---

SAMPLE_LOGCATSCOPE = """\
# .logcatscope - Define what is "in scope" for your Android app
#
# This file uses TOML format. It defines context about your app
# that can be used for smart filtering, anomaly detection, and
# focusing on relevant log entries.

[app]
# Your app's package name
package = "com.example.myapp"

# Process names to watch (main process + any background services)
processes = [
    "com.example.myapp",
    "com.example.myapp:worker",
]

[expected_tags]
# Log tags you expect from your app and key dependencies
# Logs from these tags are considered "in scope"
tags = [
    "MyApp",
    "MyAppNetwork",
    "MyAppDb",
    "ActivityManager",
    "WindowManager",
]

[expected_libs]
# Library package prefixes commonly seen in stack traces
# Used to identify relevant vs third-party code
libs = [
    "okhttp",
    "retrofit2",
    "androidx.",
    "kotlin.",
]

[stacktrace_roots]
# Package roots to consider "relevant" in stack traces
# Helps highlight your code vs framework code
roots = [
    "com.example.myapp.",
    "androidx.",
    "java.",
    "kotlin.",
]
"""


def generate_sample_scope_file(path: Path) -> bool:
    """Generate a sample .logcatscope file.

    Args:
        path: Path where the file should be created.

    Returns:
        True if file was created, False if it already exists.
    """
    if path.exists():
        return False

    path.write_text(SAMPLE_LOGCATSCOPE, encoding="utf-8")
    return True
