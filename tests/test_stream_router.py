"""Tests for stream router."""

import tempfile
from pathlib import Path

import pytest

from lcfilter.stream_router import (
    StreamTarget,
    RoutingConfig,
    StreamRouter,
)
from lcfilter.models import RouteCategory


class TestStreamTarget:
    """Tests for StreamTarget class."""

    def test_is_stdout(self):
        """Should identify stdout target."""
        assert StreamTarget("stdout").is_stdout() is True
        assert StreamTarget("stderr").is_stdout() is False
        assert StreamTarget("/dev/null").is_stdout() is False
        assert StreamTarget("output.log").is_stdout() is False

    def test_is_stderr(self):
        """Should identify stderr target."""
        assert StreamTarget("stderr").is_stderr() is True
        assert StreamTarget("stdout").is_stderr() is False
        assert StreamTarget("/dev/null").is_stderr() is False

    def test_is_devnull(self):
        """Should identify /dev/null target."""
        assert StreamTarget("/dev/null").is_devnull() is True
        assert StreamTarget("stdout").is_devnull() is False
        assert StreamTarget("output.log").is_devnull() is False

    def test_is_file(self):
        """Should identify file targets."""
        assert StreamTarget("output.log").is_file() is True
        assert StreamTarget("/path/to/file.txt").is_file() is True
        assert StreamTarget("stdout").is_file() is False
        assert StreamTarget("stderr").is_file() is False
        assert StreamTarget("/dev/null").is_file() is False


class TestRoutingConfig:
    """Tests for RoutingConfig class."""

    def test_default_config(self):
        """Default config should route in-scope and noise to stdout, ignored to /dev/null."""
        config = RoutingConfig.default()

        assert config.in_scope.is_stdout() is True
        assert config.ignored.is_devnull() is True
        assert config.noise.is_stdout() is True

    def test_from_options_defaults(self):
        """from_options with None values should use defaults."""
        config = RoutingConfig.from_options()

        assert config.in_scope.is_stdout() is True
        assert config.ignored.is_devnull() is True
        assert config.noise.is_stdout() is True

    def test_from_options_custom(self):
        """from_options should use provided values."""
        config = RoutingConfig.from_options(
            in_scope="app.log",
            ignored="ignored.log",
            noise="noise.log",
        )

        assert config.in_scope.path == "app.log"
        assert config.ignored.path == "ignored.log"
        assert config.noise.path == "noise.log"

    def test_from_options_partial(self):
        """from_options should use defaults for unspecified values."""
        config = RoutingConfig.from_options(ignored="ignored.log")

        assert config.in_scope.is_stdout() is True
        assert config.ignored.path == "ignored.log"
        assert config.noise.is_stdout() is True


class TestStreamRouter:
    """Tests for StreamRouter class."""

    def test_context_manager(self):
        """StreamRouter should work as context manager."""
        config = RoutingConfig.default()
        with StreamRouter(config) as router:
            assert router is not None

    def test_write_to_devnull(self):
        """Writing to /dev/null should succeed without error."""
        config = RoutingConfig.from_options(
            in_scope="/dev/null",
            ignored="/dev/null",
            noise="/dev/null",
        )

        with StreamRouter(config) as router:
            router.write(RouteCategory.IN_SCOPE, "test line")
            router.write(RouteCategory.IGNORED, "test line")
            router.write(RouteCategory.NOISE, "test line")

    def test_write_to_file(self):
        """Writing to file should create file with content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.log"

            config = RoutingConfig.from_options(
                in_scope=str(output_path),
                ignored="/dev/null",
                noise="/dev/null",
            )

            with StreamRouter(config) as router:
                router.write(RouteCategory.IN_SCOPE, "Line 1")
                router.write(RouteCategory.IN_SCOPE, "Line 2")

            # File should contain the written lines
            content = output_path.read_text()
            assert "Line 1" in content
            assert "Line 2" in content

    def test_write_adds_newline(self):
        """write() should add newline if not present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.log"

            config = RoutingConfig.from_options(in_scope=str(output_path))

            with StreamRouter(config) as router:
                router.write(RouteCategory.IN_SCOPE, "Line without newline")

            content = output_path.read_text()
            assert content == "Line without newline\n"

    def test_write_preserves_existing_newline(self):
        """write() should not add extra newline if already present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.log"

            config = RoutingConfig.from_options(in_scope=str(output_path))

            with StreamRouter(config) as router:
                router.write(RouteCategory.IN_SCOPE, "Line with newline\n")

            content = output_path.read_text()
            assert content == "Line with newline\n"

    def test_multiple_categories_to_different_files(self):
        """Each category should write to its configured file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            in_scope_path = Path(tmpdir) / "in_scope.log"
            ignored_path = Path(tmpdir) / "ignored.log"
            noise_path = Path(tmpdir) / "noise.log"

            config = RoutingConfig.from_options(
                in_scope=str(in_scope_path),
                ignored=str(ignored_path),
                noise=str(noise_path),
            )

            with StreamRouter(config) as router:
                router.write(RouteCategory.IN_SCOPE, "in-scope line")
                router.write(RouteCategory.IGNORED, "ignored line")
                router.write(RouteCategory.NOISE, "noise line")

            assert "in-scope line" in in_scope_path.read_text()
            assert "ignored line" in ignored_path.read_text()
            assert "noise line" in noise_path.read_text()

    def test_get_stream(self):
        """get_stream() should return the stream for a category."""
        config = RoutingConfig.default()

        with StreamRouter(config) as router:
            stream = router.get_stream(RouteCategory.IN_SCOPE)
            assert stream is not None
            assert hasattr(stream, "write")

    def test_write_entry_alias(self):
        """write_entry() should be an alias for write()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.log"

            config = RoutingConfig.from_options(in_scope=str(output_path))

            with StreamRouter(config) as router:
                router.write_entry(RouteCategory.IN_SCOPE, "Test line")

            content = output_path.read_text()
            assert "Test line" in content

    def test_files_closed_on_exit(self):
        """Files should be closed when exiting context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.log"

            config = RoutingConfig.from_options(in_scope=str(output_path))

            with StreamRouter(config) as router:
                stream = router.get_stream(RouteCategory.IN_SCOPE)

            # After context exit, opened files should be closed
            # (stdout/stderr remain open, but file handles should be closed)
            # The router's internal list should be cleared
            assert len(router._opened_files) == 0
            assert len(router._handles) == 0
