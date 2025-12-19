"""Output stream routing for three-stream filtering."""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from .models import RouteCategory


@dataclass
class StreamTarget:
    """Target for a single output stream.

    Attributes:
        path: Output path - "stdout", "stderr", "/dev/null", or file path
    """
    path: str

    def is_stdout(self) -> bool:
        return self.path == "stdout"

    def is_stderr(self) -> bool:
        return self.path == "stderr"

    def is_devnull(self) -> bool:
        return self.path == "/dev/null"

    def is_file(self) -> bool:
        return not (self.is_stdout() or self.is_stderr() or self.is_devnull())


@dataclass
class RoutingConfig:
    """Configuration for three-stream routing.

    Attributes:
        in_scope: Target for in-scope logs (default: stdout)
        ignored: Target for ignored logs (default: /dev/null)
        noise: Target for noise logs (default: stdout)
    """
    in_scope: StreamTarget
    ignored: StreamTarget
    noise: StreamTarget

    @classmethod
    def default(cls) -> "RoutingConfig":
        """Create default routing config.

        Default: in-scope and noise to stdout, ignored to /dev/null.
        """
        return cls(
            in_scope=StreamTarget("stdout"),
            ignored=StreamTarget("/dev/null"),
            noise=StreamTarget("stdout"),
        )

    @classmethod
    def from_options(
        cls,
        in_scope: str | None = None,
        ignored: str | None = None,
        noise: str | None = None,
    ) -> "RoutingConfig":
        """Create routing config from CLI options.

        Args:
            in_scope: Target for in-scope (None = stdout)
            ignored: Target for ignored (None = /dev/null)
            noise: Target for noise (None = stdout)
        """
        return cls(
            in_scope=StreamTarget(in_scope or "stdout"),
            ignored=StreamTarget(ignored or "/dev/null"),
            noise=StreamTarget(noise or "stdout"),
        )


class StreamRouter:
    """Manages multiple output streams with automatic file handle lifecycle.

    Usage:
        config = RoutingConfig.default()
        with StreamRouter(config) as router:
            for entry in entries:
                result = engine.route_entry(entry)
                router.write(result.category, entry.raw_line)
    """

    def __init__(self, config: RoutingConfig):
        self.config = config
        self._handles: dict[RouteCategory, TextIO] = {}
        self._opened_files: list[TextIO] = []

    def __enter__(self) -> "StreamRouter":
        """Open all configured streams."""
        self._handles[RouteCategory.IN_SCOPE] = self._open_stream(self.config.in_scope)
        self._handles[RouteCategory.IGNORED] = self._open_stream(self.config.ignored)
        self._handles[RouteCategory.NOISE] = self._open_stream(self.config.noise)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close any files we opened."""
        for f in self._opened_files:
            try:
                f.close()
            except Exception:
                pass  # Ignore close errors
        self._opened_files.clear()
        self._handles.clear()
        return False  # Don't suppress exceptions

    def _open_stream(self, target: StreamTarget) -> TextIO:
        """Open a stream based on target configuration."""
        if target.is_stdout():
            return sys.stdout
        elif target.is_stderr():
            return sys.stderr
        elif target.is_devnull():
            f = open("/dev/null", "w", encoding="utf-8")
            self._opened_files.append(f)
            return f
        else:
            # Regular file
            path = Path(target.path)
            f = open(path, "w", encoding="utf-8")
            self._opened_files.append(f)
            return f

    def get_stream(self, category: RouteCategory) -> TextIO:
        """Get the output stream for a category."""
        return self._handles[category]

    def write(self, category: RouteCategory, line: str) -> None:
        """Write a line to the appropriate stream.

        Args:
            category: The routing category
            line: The line to write (newline added if not present)
        """
        stream = self._handles[category]
        stream.write(line)
        if not line.endswith('\n'):
            stream.write('\n')
        stream.flush()

    def write_entry(self, category: RouteCategory, raw_line: str) -> None:
        """Write a log entry's raw line to the appropriate stream.

        Alias for write() with clearer semantics for log entries.
        """
        self.write(category, raw_line)
