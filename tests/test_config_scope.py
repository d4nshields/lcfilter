"""Tests for .logcatscope config parsing."""

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
        """Empty content should return default config."""
        config = parse_scope_content("")
        assert config.app.package == ""
        assert config.app.processes == []
        assert config.expected_tags.tags == []
        assert config.expected_libs.libs == []
        assert config.stacktrace_roots.roots == []

    def test_app_section(self):
        """Should parse [app] section."""
        content = """
        [app]
        package = "com.example.app"
        processes = ["com.example.app", "com.example.app:worker"]
        """
        config = parse_scope_content(content)
        assert config.app.package == "com.example.app"
        assert config.app.processes == ["com.example.app", "com.example.app:worker"]

    def test_expected_tags_section(self):
        """Should parse [expected_tags] section."""
        content = """
        [expected_tags]
        tags = ["MyTag", "OtherTag"]
        """
        config = parse_scope_content(content)
        assert config.expected_tags.tags == ["MyTag", "OtherTag"]

    def test_expected_libs_section(self):
        """Should parse [expected_libs] section."""
        content = """
        [expected_libs]
        libs = ["okhttp", "retrofit2"]
        """
        config = parse_scope_content(content)
        assert config.expected_libs.libs == ["okhttp", "retrofit2"]

    def test_stacktrace_roots_section(self):
        """Should parse [stacktrace_roots] section."""
        content = """
        [stacktrace_roots]
        roots = ["com.example.", "java."]
        """
        config = parse_scope_content(content)
        assert config.stacktrace_roots.roots == ["com.example.", "java."]

    def test_full_config(self):
        """Should parse a complete config file."""
        content = """
        [app]
        package = "com.example.myapp"
        processes = ["com.example.myapp"]

        [expected_tags]
        tags = ["MyApp", "Network"]

        [expected_libs]
        libs = ["okhttp"]

        [stacktrace_roots]
        roots = ["com.example."]
        """
        config = parse_scope_content(content)
        assert config.app.package == "com.example.myapp"
        assert config.app.processes == ["com.example.myapp"]
        assert config.expected_tags.tags == ["MyApp", "Network"]
        assert config.expected_libs.libs == ["okhttp"]
        assert config.stacktrace_roots.roots == ["com.example."]

    def test_invalid_toml(self):
        """Should raise ScopeParseError for invalid TOML."""
        with pytest.raises(ScopeParseError) as exc_info:
            parse_scope_content("[invalid toml")
        assert "Invalid TOML" in str(exc_info.value)

    def test_app_package_wrong_type(self):
        """Should raise error if package is not a string."""
        content = """
        [app]
        package = 123
        """
        with pytest.raises(ScopeParseError) as exc_info:
            parse_scope_content(content)
        assert "app.package" in str(exc_info.value)

    def test_app_processes_wrong_type(self):
        """Should raise error if processes is not a list."""
        content = """
        [app]
        processes = "not a list"
        """
        with pytest.raises(ScopeParseError) as exc_info:
            parse_scope_content(content)
        assert "app.processes" in str(exc_info.value)

    def test_tags_list_with_wrong_item_type(self):
        """Should raise error if tags list contains non-strings."""
        content = """
        [expected_tags]
        tags = ["valid", 123]
        """
        with pytest.raises(ScopeParseError) as exc_info:
            parse_scope_content(content)
        assert "expected_tags.tags" in str(exc_info.value)


class TestScopeConfigMethods:
    """Tests for ScopeConfig utility methods."""

    def test_is_tag_in_scope(self):
        """Should check if tag is in expected tags."""
        content = """
        [expected_tags]
        tags = ["MyApp", "Network"]
        """
        config = parse_scope_content(content)
        assert config.is_tag_in_scope("MyApp") is True
        assert config.is_tag_in_scope("Unknown") is False

    def test_is_process_in_scope(self):
        """Should check if process matches app processes."""
        content = """
        [app]
        package = "com.example.app"
        processes = ["com.example.app", "com.example.app:worker"]
        """
        config = parse_scope_content(content)
        assert config.is_process_in_scope("com.example.app") is True
        assert config.is_process_in_scope("com.example.app:worker") is True
        assert config.is_process_in_scope("com.other.app") is False

    def test_is_stacktrace_in_scope(self):
        """Should check if class name matches stacktrace roots."""
        content = """
        [stacktrace_roots]
        roots = ["com.example.", "java.lang."]
        """
        config = parse_scope_content(content)
        assert config.is_stacktrace_in_scope("com.example.MyClass") is True
        assert config.is_stacktrace_in_scope("java.lang.String") is True
        assert config.is_stacktrace_in_scope("kotlin.Unit") is False


class TestParseScopeFile:
    """Tests for parse_scope_file function."""

    def test_parse_file(self):
        """Should parse file from disk."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".logcatscope", delete=False
        ) as f:
            f.write('[app]\npackage = "com.test"\n')
            f.flush()

            config = parse_scope_file(Path(f.name))
            assert config.app.package == "com.test"

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
            assert config.app.package != ""

    def test_skips_existing(self):
        """Should not overwrite existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".logcatscope"
            path.write_text('[app]\npackage = "existing"')

            result = generate_sample_scope_file(path)
            assert result is False

            config = parse_scope_file(path)
            assert config.app.package == "existing"
