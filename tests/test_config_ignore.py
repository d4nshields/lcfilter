"""Tests for .logcatignore config parsing."""

import pytest
from pathlib import Path
import tempfile

from lcfilter.config_ignore import (
    parse_ignore_content,
    parse_ignore_file,
    parse_ignore_line,
    generate_sample_ignore_file,
    IgnoreParseError,
)
from lcfilter.models import (
    IgnoreRuleTag,
    IgnoreRuleLevel,
    IgnoreRuleTagLevel,
    IgnoreRulePattern,
    IgnoreRuleLinePattern,
    LogLevel,
)


class TestParseIgnoreLine:
    """Tests for parse_ignore_line function."""

    def test_empty_line(self):
        """Empty lines should return None."""
        assert parse_ignore_line("", 1) is None
        assert parse_ignore_line("   ", 1) is None
        assert parse_ignore_line("\t", 1) is None

    def test_comment_line(self):
        """Comment lines should return None."""
        assert parse_ignore_line("# This is a comment", 1) is None
        assert parse_ignore_line("  # Indented comment", 1) is None

    def test_tag_rule(self):
        """TAG:value should parse to IgnoreRuleTag."""
        rule = parse_ignore_line("TAG:MyTag", 1)
        assert isinstance(rule, IgnoreRuleTag)
        assert rule.tag == "MyTag"

    def test_tag_rule_with_whitespace(self):
        """TAG rule should handle whitespace."""
        rule = parse_ignore_line("  TAG:MyTag  ", 1)
        assert isinstance(rule, IgnoreRuleTag)
        assert rule.tag == "MyTag"

    def test_tag_rule_case_insensitive_prefix(self):
        """TAG prefix should be case insensitive."""
        rule = parse_ignore_line("tag:MyTag", 1)
        assert isinstance(rule, IgnoreRuleTag)
        assert rule.tag == "MyTag"

    def test_level_rule(self):
        """LEVEL:V should parse to IgnoreRuleLevel."""
        for level_str, level in [
            ("V", LogLevel.VERBOSE),
            ("D", LogLevel.DEBUG),
            ("I", LogLevel.INFO),
            ("W", LogLevel.WARNING),
            ("E", LogLevel.ERROR),
        ]:
            rule = parse_ignore_line(f"LEVEL:{level_str}", 1)
            assert isinstance(rule, IgnoreRuleLevel)
            assert rule.level == level

    def test_level_rule_lowercase(self):
        """LEVEL rule should handle lowercase level values."""
        rule = parse_ignore_line("LEVEL:d", 1)
        assert isinstance(rule, IgnoreRuleLevel)
        assert rule.level == LogLevel.DEBUG

    def test_taglevel_rule(self):
        """TAGLEVEL:Tag:Level should parse to IgnoreRuleTagLevel."""
        rule = parse_ignore_line("TAGLEVEL:MyTag:W", 1)
        assert isinstance(rule, IgnoreRuleTagLevel)
        assert rule.tag == "MyTag"
        assert rule.level == LogLevel.WARNING

    def test_pattern_rule(self):
        """PATTERN:regex should parse to IgnoreRulePattern."""
        rule = parse_ignore_line("PATTERN:GC.*freed", 1)
        assert isinstance(rule, IgnoreRulePattern)
        assert rule.pattern_str == "GC.*freed"

    def test_pattern_rule_with_colons(self):
        """PATTERN should preserve colons in regex."""
        rule = parse_ignore_line("PATTERN:time: \\d+ms", 1)
        assert isinstance(rule, IgnoreRulePattern)
        assert rule.pattern_str == "time: \\d+ms"

    def test_linepattern_rule(self):
        """LINEPATTERN:regex should parse to IgnoreRuleLinePattern."""
        rule = parse_ignore_line("LINEPATTERN:^\\d{2}-\\d{2}.*MyTag", 1)
        assert isinstance(rule, IgnoreRuleLinePattern)
        assert rule.pattern_str == "^\\d{2}-\\d{2}.*MyTag"

    def test_invalid_rule_type(self):
        """Unknown rule types should raise IgnoreParseError."""
        with pytest.raises(IgnoreParseError) as exc_info:
            parse_ignore_line("UNKNOWN:value", 1)
        assert "Unknown rule type" in str(exc_info.value)
        assert exc_info.value.line_number == 1

    def test_missing_colon(self):
        """Lines without colon should raise IgnoreParseError."""
        with pytest.raises(IgnoreParseError) as exc_info:
            parse_ignore_line("TAGMyTag", 1)
        assert "Invalid rule format" in str(exc_info.value)

    def test_empty_value(self):
        """Rules with empty values should raise IgnoreParseError."""
        with pytest.raises(IgnoreParseError) as exc_info:
            parse_ignore_line("TAG:", 1)
        assert "Empty value" in str(exc_info.value)

    def test_invalid_level(self):
        """Invalid log level should raise IgnoreParseError."""
        with pytest.raises(IgnoreParseError) as exc_info:
            parse_ignore_line("LEVEL:X", 1)
        assert "Unknown log level" in str(exc_info.value)

    def test_invalid_regex(self):
        """Invalid regex should raise IgnoreParseError."""
        with pytest.raises(IgnoreParseError) as exc_info:
            parse_ignore_line("PATTERN:[invalid", 1)
        assert "Invalid regex" in str(exc_info.value)

    def test_taglevel_wrong_format(self):
        """TAGLEVEL with wrong format should raise IgnoreParseError."""
        with pytest.raises(IgnoreParseError) as exc_info:
            parse_ignore_line("TAGLEVEL:OnlyTag", 1)
        assert "TAGLEVEL rule requires format" in str(exc_info.value)


class TestParseIgnoreContent:
    """Tests for parse_ignore_content function."""

    def test_empty_content(self):
        """Empty content should return empty config."""
        config = parse_ignore_content("")
        assert len(config.rules) == 0

    def test_only_comments(self):
        """Content with only comments should return empty config."""
        content = """
        # Comment 1
        # Comment 2
        """
        config = parse_ignore_content(content)
        assert len(config.rules) == 0

    def test_multiple_rules(self):
        """Multiple rules should all be parsed."""
        content = """
        TAG:Tag1
        TAG:Tag2
        LEVEL:V
        PATTERN:test
        """
        config = parse_ignore_content(content)
        assert len(config.rules) == 4
        assert isinstance(config.rules[0], IgnoreRuleTag)
        assert isinstance(config.rules[1], IgnoreRuleTag)
        assert isinstance(config.rules[2], IgnoreRuleLevel)
        assert isinstance(config.rules[3], IgnoreRulePattern)

    def test_mixed_with_comments(self):
        """Rules mixed with comments and blank lines."""
        content = """
        # Filter noisy tags
        TAG:NoisyTag

        # Filter verbose logs
        LEVEL:V

        # End of config
        """
        config = parse_ignore_content(content)
        assert len(config.rules) == 2


class TestParseIgnoreFile:
    """Tests for parse_ignore_file function."""

    def test_parse_file(self):
        """Should parse file from disk."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".logcatignore", delete=False
        ) as f:
            f.write("TAG:TestTag\nLEVEL:D\n")
            f.flush()

            config = parse_ignore_file(Path(f.name))
            assert len(config.rules) == 2

    def test_file_not_found(self):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_ignore_file(Path("/nonexistent/.logcatignore"))


class TestGenerateSampleIgnoreFile:
    """Tests for generate_sample_ignore_file function."""

    def test_creates_file(self):
        """Should create sample file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".logcatignore"
            result = generate_sample_ignore_file(path)
            assert result is True
            assert path.exists()

            # Should be parseable
            config = parse_ignore_file(path)
            assert len(config.rules) > 0

    def test_skips_existing(self):
        """Should not overwrite existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".logcatignore"
            path.write_text("TAG:Existing")

            result = generate_sample_ignore_file(path)
            assert result is False
            assert path.read_text() == "TAG:Existing"
