"""Tests for filter engine."""

import pytest

from lcfilter.filter_engine import (
    FilterEngine,
    FilterStats,
    create_default_engine,
    is_event_in_scope,
    is_pattern_based_rule,
)
from lcfilter.models import (
    LogEntry,
    LogLevel,
    IgnoreConfig,
    IgnoreRuleTag,
    IgnoreRuleLevel,
    IgnoreRuleTagLevel,
    IgnoreRulePattern,
    IgnoreRuleLinePattern,
    FilterResult,
    ScopeConfig,
    RouteCategory,
    RouteResult,
)


def make_entry(
    tag: str = "TestTag",
    level: LogLevel = LogLevel.INFO,
    message: str = "Test message",
    raw_line: str | None = None,
) -> LogEntry:
    """Helper to create LogEntry for testing."""
    if raw_line is None:
        raw_line = f"I/{tag}( 1234): {message}"
    return LogEntry(
        raw_line=raw_line,
        tag=tag,
        level=level,
        message=message,
        pid=1234,
    )


class TestIgnoreRuleMatching:
    """Tests for individual ignore rule matching."""

    def test_tag_rule_matches(self):
        """IgnoreRuleTag should match entries with same tag."""
        rule = IgnoreRuleTag(tag="NoisyTag")
        entry = make_entry(tag="NoisyTag")
        assert rule.matches(entry) is True

    def test_tag_rule_no_match(self):
        """IgnoreRuleTag should not match different tags."""
        rule = IgnoreRuleTag(tag="NoisyTag")
        entry = make_entry(tag="OtherTag")
        assert rule.matches(entry) is False

    def test_level_rule_matches(self):
        """IgnoreRuleLevel should match entries with same level."""
        rule = IgnoreRuleLevel(level=LogLevel.DEBUG)
        entry = make_entry(level=LogLevel.DEBUG)
        assert rule.matches(entry) is True

    def test_level_rule_no_match(self):
        """IgnoreRuleLevel should not match different levels."""
        rule = IgnoreRuleLevel(level=LogLevel.DEBUG)
        entry = make_entry(level=LogLevel.ERROR)
        assert rule.matches(entry) is False

    def test_taglevel_rule_matches(self):
        """IgnoreRuleTagLevel should match tag AND level."""
        rule = IgnoreRuleTagLevel(tag="MyTag", level=LogLevel.WARNING)
        entry = make_entry(tag="MyTag", level=LogLevel.WARNING)
        assert rule.matches(entry) is True

    def test_taglevel_rule_wrong_tag(self):
        """IgnoreRuleTagLevel should not match wrong tag."""
        rule = IgnoreRuleTagLevel(tag="MyTag", level=LogLevel.WARNING)
        entry = make_entry(tag="OtherTag", level=LogLevel.WARNING)
        assert rule.matches(entry) is False

    def test_taglevel_rule_wrong_level(self):
        """IgnoreRuleTagLevel should not match wrong level."""
        rule = IgnoreRuleTagLevel(tag="MyTag", level=LogLevel.WARNING)
        entry = make_entry(tag="MyTag", level=LogLevel.ERROR)
        assert rule.matches(entry) is False

    def test_pattern_rule_matches(self):
        """IgnoreRulePattern should match message content."""
        rule = IgnoreRulePattern(pattern_str="GC.*freed")
        entry = make_entry(message="GC concurrent freed 1234 bytes")
        assert rule.matches(entry) is True

    def test_pattern_rule_partial_match(self):
        """IgnoreRulePattern should match partial message."""
        rule = IgnoreRulePattern(pattern_str="error")
        entry = make_entry(message="An error occurred here")
        assert rule.matches(entry) is True

    def test_pattern_rule_no_match(self):
        """IgnoreRulePattern should not match non-matching message."""
        rule = IgnoreRulePattern(pattern_str="error")
        entry = make_entry(message="Everything is fine")
        assert rule.matches(entry) is False

    def test_linepattern_rule_matches(self):
        """IgnoreRuleLinePattern should match raw line."""
        rule = IgnoreRuleLinePattern(pattern_str="^D/.*NoisyTag")
        entry = make_entry(
            tag="NoisyTag",
            level=LogLevel.DEBUG,
            raw_line="D/NoisyTag( 1234): message",
        )
        assert rule.matches(entry) is True

    def test_linepattern_rule_no_match(self):
        """IgnoreRuleLinePattern should not match non-matching line."""
        rule = IgnoreRuleLinePattern(pattern_str="^E/")
        entry = make_entry(raw_line="D/Tag( 1234): message")
        assert rule.matches(entry) is False


class TestFilterEngine:
    """Tests for FilterEngine class."""

    def test_no_rules_shows_all(self):
        """With no rules, all entries should be displayed."""
        engine = FilterEngine()
        entry = make_entry()
        result = engine.filter_entry(entry)

        assert result.should_display is True
        assert result.matched_rule is None

    def test_matching_rule_hides_entry(self):
        """Matching rule should hide entry."""
        config = IgnoreConfig()
        config.add_rule(IgnoreRuleTag(tag="HiddenTag"))

        engine = FilterEngine(ignore_config=config)
        entry = make_entry(tag="HiddenTag")
        result = engine.filter_entry(entry)

        assert result.should_display is False
        assert result.matched_rule is not None

    def test_non_matching_rule_shows_entry(self):
        """Non-matching rule should show entry."""
        config = IgnoreConfig()
        config.add_rule(IgnoreRuleTag(tag="HiddenTag"))

        engine = FilterEngine(ignore_config=config)
        entry = make_entry(tag="VisibleTag")
        result = engine.filter_entry(entry)

        assert result.should_display is True
        assert result.matched_rule is None

    def test_multiple_rules_first_match_wins(self):
        """First matching rule should be returned."""
        config = IgnoreConfig()
        config.add_rule(IgnoreRuleLevel(level=LogLevel.DEBUG))
        config.add_rule(IgnoreRuleTag(tag="MyTag"))

        engine = FilterEngine(ignore_config=config)
        entry = make_entry(tag="MyTag", level=LogLevel.DEBUG)
        result = engine.filter_entry(entry)

        assert result.should_display is False
        assert isinstance(result.matched_rule, IgnoreRuleLevel)

    def test_filter_entries_generator(self):
        """filter_entries should yield FilterResult for each entry."""
        config = IgnoreConfig()
        config.add_rule(IgnoreRuleTag(tag="Hidden"))

        engine = FilterEngine(ignore_config=config)
        entries = [
            make_entry(tag="Hidden"),
            make_entry(tag="Visible"),
            make_entry(tag="Hidden"),
        ]

        results = list(engine.filter_entries(iter(entries)))

        assert len(results) == 3
        assert results[0].should_display is False
        assert results[1].should_display is True
        assert results[2].should_display is False

    def test_filter_and_yield_visible(self):
        """filter_and_yield_visible should only yield visible entries."""
        config = IgnoreConfig()
        config.add_rule(IgnoreRuleTag(tag="Hidden"))

        engine = FilterEngine(ignore_config=config)
        entries = [
            make_entry(tag="Hidden"),
            make_entry(tag="Visible1"),
            make_entry(tag="Hidden"),
            make_entry(tag="Visible2"),
        ]

        visible = list(engine.filter_and_yield_visible(iter(entries)))

        assert len(visible) == 2
        assert visible[0].tag == "Visible1"
        assert visible[1].tag == "Visible2"


class TestFilterEngineHooks:
    """Tests for FilterEngine pre/post filter hooks."""

    def test_pre_filter_can_override(self):
        """Pre-filter returning result should skip ignore rules."""

        def always_hide(entry: LogEntry) -> FilterResult | None:
            if entry.tag == "ForceHide":
                return FilterResult(entry=entry, should_display=False)
            return None

        engine = FilterEngine()
        engine.add_pre_filter(always_hide)

        # This would normally be shown (no ignore rules)
        entry = make_entry(tag="ForceHide")
        result = engine.filter_entry(entry)

        assert result.should_display is False

    def test_pre_filter_returns_none_continues(self):
        """Pre-filter returning None should continue to ignore rules."""

        def noop_filter(entry: LogEntry) -> FilterResult | None:
            return None

        config = IgnoreConfig()
        config.add_rule(IgnoreRuleTag(tag="Hidden"))

        engine = FilterEngine(ignore_config=config)
        engine.add_pre_filter(noop_filter)

        entry = make_entry(tag="Hidden")
        result = engine.filter_entry(entry)

        assert result.should_display is False

    def test_post_filter_can_modify(self):
        """Post-filter can modify the result."""

        def force_show(result: FilterResult) -> FilterResult:
            # Force show entries with ERROR level
            if result.entry.level == LogLevel.ERROR:
                return FilterResult(
                    entry=result.entry,
                    should_display=True,
                    matched_rule=result.matched_rule,
                )
            return result

        config = IgnoreConfig()
        config.add_rule(IgnoreRuleLevel(level=LogLevel.ERROR))  # Would hide errors

        engine = FilterEngine(ignore_config=config)
        engine.add_post_filter(force_show)

        entry = make_entry(level=LogLevel.ERROR)
        result = engine.filter_entry(entry)

        # Post-filter overrode the ignore rule
        assert result.should_display is True


class TestFilterStats:
    """Tests for FilterStats class."""

    def test_initial_values(self):
        """Stats should start at zero."""
        stats = FilterStats()
        assert stats.total_entries == 0
        assert stats.displayed_entries == 0
        assert stats.ignored_entries == 0

    def test_record_displayed(self):
        """Should count displayed entries."""
        stats = FilterStats()
        result = FilterResult(
            entry=make_entry(),
            should_display=True,
        )
        stats.record(result)

        assert stats.total_entries == 1
        assert stats.displayed_entries == 1
        assert stats.ignored_entries == 0

    def test_record_ignored(self):
        """Should count ignored entries and track rules."""
        stats = FilterStats()
        rule = IgnoreRuleTag(tag="Test")
        result = FilterResult(
            entry=make_entry(),
            should_display=False,
            matched_rule=rule,
        )
        stats.record(result)

        assert stats.total_entries == 1
        assert stats.displayed_entries == 0
        assert stats.ignored_entries == 1
        assert len(stats.rule_match_counts) == 1

    def test_filter_rate(self):
        """Should calculate correct filter rate."""
        stats = FilterStats()

        # Record 3 displayed, 7 ignored
        for _ in range(3):
            stats.record(FilterResult(entry=make_entry(), should_display=True))
        for _ in range(7):
            stats.record(
                FilterResult(
                    entry=make_entry(),
                    should_display=False,
                    matched_rule=IgnoreRuleTag(tag="x"),
                )
            )

        assert stats.filter_rate == 70.0

    def test_filter_rate_zero_entries(self):
        """Filter rate should be 0 with no entries."""
        stats = FilterStats()
        assert stats.filter_rate == 0.0

    def test_summary(self):
        """Summary should include key information."""
        stats = FilterStats()
        stats.record(FilterResult(entry=make_entry(), should_display=True))
        stats.record(
            FilterResult(
                entry=make_entry(),
                should_display=False,
                matched_rule=IgnoreRuleTag(tag="Test"),
            )
        )

        summary = stats.summary()

        assert "Total entries: 2" in summary
        assert "Displayed: 1" in summary
        assert "Ignored: 1" in summary


class TestCreateDefaultEngine:
    """Tests for create_default_engine factory."""

    def test_creates_engine(self):
        """Should create a working FilterEngine."""
        engine = create_default_engine()
        assert isinstance(engine, FilterEngine)

    def test_accepts_configs(self):
        """Should accept ignore and scope configs."""
        config = IgnoreConfig()
        config.add_rule(IgnoreRuleTag(tag="Test"))

        engine = create_default_engine(ignore_config=config)
        entry = make_entry(tag="Test")
        result = engine.filter_entry(entry)

        assert result.should_display is False


class TestIsEventInScope:
    """Tests for is_event_in_scope helper function."""

    def test_none_scope_returns_false(self):
        """With no scope config, events are not in scope."""
        entry = make_entry(tag="MyApp")
        assert is_event_in_scope(entry, None) is False

    def test_empty_expected_tags_returns_false(self):
        """With empty expected_tags, events are not in scope."""
        scope = ScopeConfig()
        entry = make_entry(tag="MyApp")
        assert is_event_in_scope(entry, scope) is False

    def test_tag_in_expected_tags_returns_true(self):
        """Events with tags in scope are in scope."""
        scope = ScopeConfig(tags={"MyApp", "MyAppNetwork"})
        entry = make_entry(tag="MyApp")
        assert is_event_in_scope(entry, scope) is True

    def test_tag_not_in_expected_tags_returns_false(self):
        """Events with tags not in scope are not in scope."""
        scope = ScopeConfig(tags={"MyApp", "MyAppNetwork"})
        entry = make_entry(tag="SystemServer")
        assert is_event_in_scope(entry, scope) is False

    def test_none_tag_returns_false(self):
        """Events with None tag are not in scope."""
        scope = ScopeConfig(tags={"MyApp"})
        entry = LogEntry(raw_line="some line", tag=None)
        assert is_event_in_scope(entry, scope) is False

    def test_empty_tag_returns_false(self):
        """Events with empty tag are not in scope."""
        scope = ScopeConfig(tags={"MyApp"})
        entry = LogEntry(raw_line="some line", tag="")
        assert is_event_in_scope(entry, scope) is False


class TestIsPatternBasedRule:
    """Tests for is_pattern_based_rule helper function."""

    def test_pattern_rule_is_pattern_based(self):
        """IgnoreRulePattern is pattern-based."""
        rule = IgnoreRulePattern(pattern_str="test")
        assert is_pattern_based_rule(rule) is True

    def test_linepattern_rule_is_pattern_based(self):
        """IgnoreRuleLinePattern is pattern-based."""
        rule = IgnoreRuleLinePattern(pattern_str="test")
        assert is_pattern_based_rule(rule) is True

    def test_tag_rule_is_not_pattern_based(self):
        """IgnoreRuleTag is not pattern-based."""
        rule = IgnoreRuleTag(tag="Test")
        assert is_pattern_based_rule(rule) is False

    def test_level_rule_is_not_pattern_based(self):
        """IgnoreRuleLevel is not pattern-based."""
        rule = IgnoreRuleLevel(level=LogLevel.DEBUG)
        assert is_pattern_based_rule(rule) is False

    def test_taglevel_rule_is_not_pattern_based(self):
        """IgnoreRuleTagLevel is not pattern-based."""
        rule = IgnoreRuleTagLevel(tag="Test", level=LogLevel.DEBUG)
        assert is_pattern_based_rule(rule) is False


class TestScopeAwareFiltering:
    """Tests for scope-aware filtering behavior."""

    def make_scope_with_tags(self, tags: list[str]) -> ScopeConfig:
        """Helper to create a ScopeConfig with expected tags."""
        return ScopeConfig(tags=set(tags))

    def test_in_scope_event_not_hidden_by_level_rule(self):
        """In-scope events should NOT be hidden by LEVEL rules."""
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRuleLevel(level=LogLevel.DEBUG))

        scope_config = self.make_scope_with_tags(["MyApp"])

        engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)
        entry = make_entry(tag="MyApp", level=LogLevel.DEBUG)
        result = engine.filter_entry(entry)

        # In-scope event should be shown despite matching LEVEL:D rule
        assert result.should_display is True
        assert result.matched_rule is None

    def test_in_scope_event_not_hidden_by_tag_rule(self):
        """In-scope events should NOT be hidden by TAG rules."""
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRuleTag(tag="MyApp"))

        scope_config = self.make_scope_with_tags(["MyApp"])

        engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)
        entry = make_entry(tag="MyApp")
        result = engine.filter_entry(entry)

        # In-scope event should be shown despite matching TAG rule
        assert result.should_display is True
        assert result.matched_rule is None

    def test_in_scope_event_not_hidden_by_taglevel_rule(self):
        """In-scope events should NOT be hidden by TAGLEVEL rules."""
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRuleTagLevel(tag="MyApp", level=LogLevel.DEBUG))

        scope_config = self.make_scope_with_tags(["MyApp"])

        engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)
        entry = make_entry(tag="MyApp", level=LogLevel.DEBUG)
        result = engine.filter_entry(entry)

        # In-scope event should be shown despite matching TAGLEVEL rule
        assert result.should_display is True
        assert result.matched_rule is None

    def test_in_scope_event_can_be_hidden_by_pattern_rule(self):
        """In-scope events CAN be hidden by PATTERN rules."""
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRulePattern(pattern_str="noisy message"))

        scope_config = self.make_scope_with_tags(["MyApp"])

        engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)
        entry = make_entry(tag="MyApp", message="This is a noisy message to ignore")
        result = engine.filter_entry(entry)

        # In-scope event should be hidden by matching PATTERN rule
        assert result.should_display is False
        assert isinstance(result.matched_rule, IgnoreRulePattern)

    def test_in_scope_event_can_be_hidden_by_linepattern_rule(self):
        """In-scope events CAN be hidden by LINEPATTERN rules."""
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRuleLinePattern(pattern_str="NOISY_LINE"))

        scope_config = self.make_scope_with_tags(["MyApp"])

        engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)
        entry = make_entry(
            tag="MyApp",
            raw_line="D/MyApp( 1234): NOISY_LINE should be filtered",
        )
        result = engine.filter_entry(entry)

        # In-scope event should be hidden by matching LINEPATTERN rule
        assert result.should_display is False
        assert isinstance(result.matched_rule, IgnoreRuleLinePattern)

    def test_out_of_scope_event_hidden_by_level_rule(self):
        """Out-of-scope events SHOULD be hidden by LEVEL rules."""
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRuleLevel(level=LogLevel.DEBUG))

        scope_config = self.make_scope_with_tags(["MyApp"])

        engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)
        entry = make_entry(tag="SystemServer", level=LogLevel.DEBUG)
        result = engine.filter_entry(entry)

        # Out-of-scope event should be hidden by LEVEL rule
        assert result.should_display is False
        assert isinstance(result.matched_rule, IgnoreRuleLevel)

    def test_out_of_scope_event_hidden_by_tag_rule(self):
        """Out-of-scope events SHOULD be hidden by TAG rules."""
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRuleTag(tag="chatty"))

        scope_config = self.make_scope_with_tags(["MyApp"])

        engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)
        entry = make_entry(tag="chatty")
        result = engine.filter_entry(entry)

        # Out-of-scope event should be hidden by TAG rule
        assert result.should_display is False
        assert isinstance(result.matched_rule, IgnoreRuleTag)

    def test_no_scope_config_all_rules_apply(self):
        """With no scope config, all rules apply (backward compatibility)."""
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRuleLevel(level=LogLevel.DEBUG))

        engine = FilterEngine(ignore_config=ignore_config, scope_config=None)
        entry = make_entry(tag="MyApp", level=LogLevel.DEBUG)
        result = engine.filter_entry(entry)

        # Without scope, LEVEL rule should hide the entry
        assert result.should_display is False
        assert isinstance(result.matched_rule, IgnoreRuleLevel)

    def test_mixed_rules_in_scope_only_patterns_apply(self):
        """With mixed rules, only pattern rules apply to in-scope events."""
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRuleLevel(level=LogLevel.VERBOSE))
        ignore_config.add_rule(IgnoreRuleLevel(level=LogLevel.DEBUG))
        ignore_config.add_rule(IgnoreRuleTag(tag="chatty"))
        ignore_config.add_rule(IgnoreRulePattern(pattern_str="GC.*freed"))

        scope_config = self.make_scope_with_tags(["MyApp"])
        engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)

        # In-scope DEBUG entry without GC message - should be shown
        entry1 = make_entry(tag="MyApp", level=LogLevel.DEBUG, message="Starting up")
        result1 = engine.filter_entry(entry1)
        assert result1.should_display is True

        # In-scope entry with GC message - should be hidden by PATTERN
        entry2 = make_entry(tag="MyApp", message="GC concurrent freed 1234 bytes")
        result2 = engine.filter_entry(entry2)
        assert result2.should_display is False
        assert isinstance(result2.matched_rule, IgnoreRulePattern)

        # Out-of-scope DEBUG entry - should be hidden by LEVEL
        entry3 = make_entry(tag="SystemServer", level=LogLevel.DEBUG)
        result3 = engine.filter_entry(entry3)
        assert result3.should_display is False
        assert isinstance(result3.matched_rule, IgnoreRuleLevel)

    def test_verbose_logs_from_app_shown_when_in_scope(self):
        """Real-world scenario: V/D logs from app should be visible."""
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRuleLevel(level=LogLevel.VERBOSE))
        ignore_config.add_rule(IgnoreRuleLevel(level=LogLevel.DEBUG))

        scope_config = self.make_scope_with_tags(["MyApp", "MyAppNetwork", "MyAppDb"])
        engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)

        # Verbose log from app - should be shown
        entry1 = make_entry(tag="MyApp", level=LogLevel.VERBOSE, message="Trace log")
        assert engine.filter_entry(entry1).should_display is True

        # Debug log from app network module - should be shown
        entry2 = make_entry(tag="MyAppNetwork", level=LogLevel.DEBUG, message="Request sent")
        assert engine.filter_entry(entry2).should_display is True

        # Verbose log from system - should be hidden
        entry3 = make_entry(tag="ActivityManager", level=LogLevel.VERBOSE)
        assert engine.filter_entry(entry3).should_display is False

        # Info log from system - should be shown (no rule for INFO)
        entry4 = make_entry(tag="ActivityManager", level=LogLevel.INFO)
        assert engine.filter_entry(entry4).should_display is True


class TestRouteEntry:
    """Tests for FilterEngine.route_entry() method."""

    def test_in_scope_tag_routes_to_in_scope(self):
        """Tag in scope config should route to IN_SCOPE."""
        scope_config = ScopeConfig(tags={"MyApp"})
        engine = FilterEngine(scope_config=scope_config)

        entry = make_entry(tag="MyApp")
        result = engine.route_entry(entry)

        assert result.category == RouteCategory.IN_SCOPE
        assert result.matched_rule is None

    def test_ignored_entry_routes_to_ignored(self):
        """Entry matching ignore rule should route to IGNORED."""
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRuleTag(tag="chatty"))

        engine = FilterEngine(ignore_config=ignore_config)
        entry = make_entry(tag="chatty")
        result = engine.route_entry(entry)

        assert result.category == RouteCategory.IGNORED
        assert isinstance(result.matched_rule, IgnoreRuleTag)

    def test_unmatched_entry_routes_to_noise(self):
        """Entry not matching anything should route to NOISE."""
        scope_config = ScopeConfig(tags={"MyApp"})
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRuleTag(tag="chatty"))

        engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)
        entry = make_entry(tag="SystemServer")  # Not in scope, not ignored
        result = engine.route_entry(entry)

        assert result.category == RouteCategory.NOISE
        assert result.matched_rule is None

    def test_in_scope_takes_priority_over_ignored(self):
        """In-scope should take priority even if entry would match ignore rule."""
        scope_config = ScopeConfig(tags={"MyApp"})
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRuleTag(tag="MyApp"))  # Same tag

        engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)
        entry = make_entry(tag="MyApp")
        result = engine.route_entry(entry)

        # Should be IN_SCOPE, not IGNORED
        assert result.category == RouteCategory.IN_SCOPE

    def test_level_ignore_rule_routes_correctly(self):
        """LEVEL ignore rule should route out-of-scope entries to IGNORED."""
        scope_config = ScopeConfig(tags={"MyApp"})
        ignore_config = IgnoreConfig()
        ignore_config.add_rule(IgnoreRuleLevel(level=LogLevel.DEBUG))

        engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)

        # Out-of-scope DEBUG -> IGNORED
        entry1 = make_entry(tag="SystemServer", level=LogLevel.DEBUG)
        assert engine.route_entry(entry1).category == RouteCategory.IGNORED

        # In-scope DEBUG -> IN_SCOPE (level rule doesn't apply)
        entry2 = make_entry(tag="MyApp", level=LogLevel.DEBUG)
        assert engine.route_entry(entry2).category == RouteCategory.IN_SCOPE

        # Out-of-scope INFO -> NOISE (no rule for INFO)
        entry3 = make_entry(tag="SystemServer", level=LogLevel.INFO)
        assert engine.route_entry(entry3).category == RouteCategory.NOISE

    def test_empty_configs_routes_all_to_noise(self):
        """With empty configs, all entries should route to NOISE."""
        engine = FilterEngine()
        entry = make_entry()
        result = engine.route_entry(entry)

        assert result.category == RouteCategory.NOISE

    def test_route_result_contains_entry(self):
        """RouteResult should contain the original entry."""
        engine = FilterEngine()
        entry = make_entry(tag="TestTag", message="Test message")
        result = engine.route_entry(entry)

        assert result.entry is entry
        assert result.entry.tag == "TestTag"
        assert result.entry.message == "Test message"
