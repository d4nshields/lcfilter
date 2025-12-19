"""Parser for .logcatscope configuration files (simple line-based format)."""

from pathlib import Path

from .models import ScopeConfig


class ScopeParseError(Exception):
    """Error parsing .logcatscope file."""

    def __init__(self, message: str, line_number: int | None = None):
        self.line_number = line_number
        if line_number:
            super().__init__(f"Line {line_number}: {message}")
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

    Format:
        - One tag per line
        - Lines starting with # are comments
        - Empty lines and whitespace-only lines are ignored
        - Leading/trailing whitespace on tags is trimmed

    Args:
        content: The raw content of a .logcatscope file.

    Returns:
        Parsed ScopeConfig.

    Raises:
        ScopeParseError: If the content is invalid.
    """
    tags: set[str] = set()

    for line_number, line in enumerate(content.splitlines(), start=1):
        # Strip whitespace
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Skip comments
        if line.startswith("#"):
            continue

        # Validate tag (no spaces allowed in tag names)
        if " " in line or "\t" in line:
            raise ScopeParseError(
                f"Invalid tag '{line}' - tags cannot contain whitespace",
                line_number=line_number,
            )

        # Add the tag
        tags.add(line)

    return ScopeConfig(tags=tags)


# --- Sample file generation ---

SAMPLE_LOGCATSCOPE = """\
# .logcatscope - Tags that belong to your app
#
# List one tag per line. Logs from these tags are considered "in scope"
# and will be routed to the in-scope output stream.
#
# Lines starting with # are comments.
# Empty lines are ignored.

# Your app's log tags
MyApp
MyAppNetwork
MyAppDb

# Framework tags you want to see
flutter
ActivityManager
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
