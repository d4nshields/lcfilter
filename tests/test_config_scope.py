"""Tests for .logcatscope config parsing (line-based format)."""

import pytest
from pathlib import Path
import tempfile

from lcfilter.config_scope import (
    parse_scope_content,
    parse_scope_file,
    generate_sample_scope_file,
    ScopeParseError,
)


class TestParseScopeContent:
    """Tests for parse_scope_content function."""

    def test_empty_content(self):
        """Empty content should return config with empty tags."""
        config = parse_scope_content("")
        assert config.tags == set()

    def test_single_tag(self):
        """Should parse a single tag."""
        config = parse_scope_content("MyApp")
        assert config.tags == {"MyApp"}

    def test_multiple_tags(self):
        """Should parse multiple tags."""
        content = """
MyApp
MyAppNetwork
MyAppDb
"""
        config = parse_scope_content(content)
        assert config.tags == {"MyApp", "MyAppNetwork", "MyAppDb"}

    def test_comments_ignored(self):
        """Lines starting with # should be ignored."""
        content = """
# This is a comment
MyApp
# Another comment
MyAppNetwork
"""
        config = parse_scope_content(content)
        assert config.tags == {"MyApp", "MyAppNetwork"}

    def test_empty_lines_ignored(self):
        """Empty lines and whitespace-only lines should be ignored."""
        content = """
MyApp


MyAppNetwork

"""
        config = parse_scope_content(content)
        assert config.tags == {"MyApp", "MyAppNetwork"}

    def test_whitespace_trimmed(self):
        """Leading/trailing whitespace on tags should be trimmed."""
        content = """
  MyApp
    MyAppNetwork
"""
        config = parse_scope_content(content)
        assert config.tags == {"MyApp", "MyAppNetwork"}

    def test_duplicate_tags_deduplicated(self):
        """Duplicate tags should result in a single entry."""
        content = """
MyApp
MyApp
MyAppNetwork
MyApp
"""
        config = parse_scope_content(content)
        assert config.tags == {"MyApp", "MyAppNetwork"}

    def test_tag_with_space_raises_error(self):
        """Tags containing spaces should raise ScopeParseError."""
        content = "MyApp Network"
        with pytest.raises(ScopeParseError) as exc_info:
            parse_scope_content(content)
        assert "whitespace" in str(exc_info.value).lower()
        assert exc_info.value.line_number == 1

    def test_tag_with_tab_raises_error(self):
        """Tags containing tabs should raise ScopeParseError."""
        content = "MyApp\tNetwork"
        with pytest.raises(ScopeParseError) as exc_info:
            parse_scope_content(content)
        assert "whitespace" in str(exc_info.value).lower()

    def test_error_includes_line_number(self):
        """Parse errors should include the line number."""
        content = """
MyApp
Invalid Tag Here
MyAppNetwork
"""
        with pytest.raises(ScopeParseError) as exc_info:
            parse_scope_content(content)
        assert exc_info.value.line_number == 3

    def test_real_world_config(self):
        """Should parse a realistic config file."""
        content = """
# .logcatscope - Tags that belong to my app
# One tag per line

# Main app tags
MyApp
MyAppNetwork
MyAppDb

# Flutter tags
flutter

# Third-party libraries
OkHttp
Retrofit
"""
        config = parse_scope_content(content)
        assert config.tags == {
            "MyApp",
            "MyAppNetwork",
            "MyAppDb",
            "flutter",
            "OkHttp",
            "Retrofit",
        }


class TestScopeConfigMethods:
    """Tests for ScopeConfig utility methods."""

    def test_is_tag_in_scope(self):
        """Should check if tag is in the tags set."""
        content = """
MyApp
Network
"""
        config = parse_scope_content(content)
        assert config.is_tag_in_scope("MyApp") is True
        assert config.is_tag_in_scope("Network") is True
        assert config.is_tag_in_scope("Unknown") is False

    def test_is_tag_in_scope_empty_config(self):
        """Empty config should return False for all tags."""
        config = parse_scope_content("")
        assert config.is_tag_in_scope("MyApp") is False


class TestParseScopeFile:
    """Tests for parse_scope_file function."""

    def test_parse_file(self):
        """Should parse file from disk."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".logcatscope", delete=False
        ) as f:
            f.write("MyApp\nMyAppNetwork\n")
            f.flush()

            config = parse_scope_file(Path(f.name))
            assert config.tags == {"MyApp", "MyAppNetwork"}

    def test_file_not_found(self):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_scope_file(Path("/nonexistent/.logcatscope"))


class TestGenerateSampleScopeFile:
    """Tests for generate_sample_scope_file function."""

    def test_creates_file(self):
        """Should create sample file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".logcatscope"
            result = generate_sample_scope_file(path)
            assert result is True
            assert path.exists()

            # Should be parseable
            config = parse_scope_file(path)
            # Sample should have some tags
            assert len(config.tags) > 0

    def test_skips_existing(self):
        """Should not overwrite existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".logcatscope"
            path.write_text("ExistingTag\n")

            result = generate_sample_scope_file(path)
            assert result is False

            config = parse_scope_file(path)
            assert config.tags == {"ExistingTag"}

    def test_sample_file_parseable(self):
        """Sample file should parse without errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".logcatscope"
            generate_sample_scope_file(path)

            # Should not raise
            config = parse_scope_file(path)
            assert isinstance(config.tags, set)
