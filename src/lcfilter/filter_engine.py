"""Filter engine for applying ignore rules to log entries."""

from typing import Iterator, Callable

from .models import (
    LogEntry,
    IgnoreConfig,
    IgnoreRule,
    IgnoreRulePattern,
    IgnoreRuleLinePattern,
    ScopeConfig,
    FilterResult,
    RouteCategory,
    RouteResult,
)


def is_event_in_scope(entry: LogEntry, scope: ScopeConfig | None) -> bool:
    """Check if a log entry is considered "in scope" for the current project.

    An event is considered in-scope if its tag appears in the scope's
    tags set. In-scope events are routed to the InScope output stream.

    Args:
        entry: The log entry to check.
        scope: The scope configuration, or None.

    Returns:
        True if the event is in scope, False otherwise.
    """
    if scope is None:
        return False

    tag = entry.tag or ""
    if not tag:
        return False

    return tag in scope.tags


def is_pattern_based_rule(rule: IgnoreRule) -> bool:
    """Check if a rule is pattern-based (PATTERN or LINEPATTERN).

    Pattern-based rules apply to all events, including in-scope events.
    Non-pattern rules (TAG, LEVEL, TAGLEVEL) are skipped for in-scope events.

    Args:
        rule: The ignore rule to check.

    Returns:
        True if the rule is pattern-based.
    """
    return isinstance(rule, (IgnoreRulePattern, IgnoreRuleLinePattern))


class FilterEngine:
    """Engine for filtering log entries based on ignore rules.

    The FilterEngine applies ignore rules from .logcatignore files to
    log entries and determines which entries should be displayed.

    This class is designed for extensibility:
    - Supports custom filter functions via hooks
    - Maintains scope config for future anomaly detection
    - Returns FilterResult objects with metadata for routing

    Attributes:
        ignore_config: The parsed .logcatignore configuration.
        scope_config: The parsed .logcatscope configuration (optional).
    """

    def __init__(
        self,
        ignore_config: IgnoreConfig | None = None,
        scope_config: ScopeConfig | None = None,
    ) -> None:
        """Initialize the filter engine.

        Args:
            ignore_config: Parsed ignore rules. Defaults to empty config.
            scope_config: Parsed scope config for context-aware filtering.
        """
        self.ignore_config = ignore_config or IgnoreConfig()
        self.scope_config = scope_config or ScopeConfig()

        # Extension point: custom filter hooks
        self._pre_filters: list[Callable[[LogEntry], FilterResult | None]] = []
        self._post_filters: list[Callable[[FilterResult], FilterResult]] = []

    def add_pre_filter(
        self, hook: Callable[[LogEntry], FilterResult | None]
    ) -> None:
        """Add a pre-filter hook.

        Pre-filters run before ignore rules. If a pre-filter returns
        a FilterResult, that result is used and ignore rules are skipped.
        Return None to continue to normal processing.

        Args:
            hook: Function that takes LogEntry and optionally returns FilterResult.
        """
        self._pre_filters.append(hook)

    def add_post_filter(
        self, hook: Callable[[FilterResult], FilterResult]
    ) -> None:
        """Add a post-filter hook.

        Post-filters run after ignore rules and can modify the result.
        This is useful for anomaly detection, severity adjustment, etc.

        Args:
            hook: Function that takes and returns FilterResult.
        """
        self._post_filters.append(hook)

    def filter_entry(self, entry: LogEntry) -> FilterResult:
        """Filter a single log entry.

        Args:
            entry: The log entry to filter.

        Returns:
            FilterResult indicating whether to display and metadata.
        """
        # Run pre-filters
        for pre_filter in self._pre_filters:
            result = pre_filter(entry)
            if result is not None:
                return self._apply_post_filters(result)

        # Check ignore rules
        matched_rule = self._check_ignore_rules(entry)

        result = FilterResult(
            entry=entry,
            should_display=matched_rule is None,
            matched_rule=matched_rule,
        )

        return self._apply_post_filters(result)

    def route_entry(self, entry: LogEntry) -> RouteResult:
        """Route a log entry to one of three categories.

        Routing logic (hierarchical):
        1. Is tag in scope? -> IN_SCOPE
        2. Does it match any ignore rule? -> IGNORED
        3. Otherwise -> NOISE

        This is simpler than filter_entry() because in-scope logs
        always go to IN_SCOPE regardless of ignore rules.

        Args:
            entry: The log entry to route.

        Returns:
            RouteResult with category and optional matched rule.
        """
        # First check: Is this in-scope?
        if is_event_in_scope(entry, self.scope_config):
            return RouteResult(entry=entry, category=RouteCategory.IN_SCOPE)

        # Second check: Does it match any ignore rule?
        # For out-of-scope, check ALL rules (not just pattern-based)
        for rule in self.ignore_config.rules:
            if rule.matches(entry):
                return RouteResult(
                    entry=entry,
                    category=RouteCategory.IGNORED,
                    matched_rule=rule,
                )

        # Default: noise
        return RouteResult(entry=entry, category=RouteCategory.NOISE)

    def _check_ignore_rules(self, entry: LogEntry) -> IgnoreRule | None:
        """Check if any ignore rule matches the entry.

        For in-scope events (tag in scope.tags), only pattern-based
        rules (PATTERN, LINEPATTERN) are applied. TAG, LEVEL, and TAGLEVEL
        rules are skipped for in-scope events.

        For out-of-scope events, all rules are applied as normal.

        Args:
            entry: The log entry to check.

        Returns:
            The first matching rule, or None if no rules match.
        """
        in_scope = is_event_in_scope(entry, self.scope_config)

        for rule in self.ignore_config.rules:
            # For in-scope events, skip non-pattern rules
            if in_scope and not is_pattern_based_rule(rule):
                continue

            if rule.matches(entry):
                return rule
        return None

    def _apply_post_filters(self, result: FilterResult) -> FilterResult:
        """Apply post-filter hooks to the result."""
        for post_filter in self._post_filters:
            result = post_filter(result)
        return result

    def filter_entries(
        self, entries: Iterator[LogEntry]
    ) -> Iterator[FilterResult]:
        """Filter multiple log entries.

        Args:
            entries: Iterator of log entries.

        Yields:
            FilterResult for each entry.
        """
        for entry in entries:
            yield self.filter_entry(entry)

    def filter_and_yield_visible(
        self, entries: Iterator[LogEntry]
    ) -> Iterator[LogEntry]:
        """Filter entries and yield only those that should be displayed.

        This is a convenience method for simple filtering use cases.

        Args:
            entries: Iterator of log entries.

        Yields:
            LogEntry objects that should be displayed.
        """
        for result in self.filter_entries(entries):
            if result.should_display:
                yield result.entry


def create_default_engine(
    ignore_config: IgnoreConfig | None = None,
    scope_config: ScopeConfig | None = None,
) -> FilterEngine:
    """Create a FilterEngine with default configuration.

    This factory function creates a ready-to-use filter engine.
    Future versions may add default hooks for common functionality.

    Args:
        ignore_config: Parsed ignore rules.
        scope_config: Parsed scope config.

    Returns:
        Configured FilterEngine instance.
    """
    return FilterEngine(
        ignore_config=ignore_config,
        scope_config=scope_config,
    )


class FilterStats:
    """Statistics tracker for filter operations.

    Useful for reporting filter effectiveness and debugging rules.
    """

    def __init__(self) -> None:
        self.total_entries: int = 0
        self.displayed_entries: int = 0
        self.ignored_entries: int = 0
        self.rule_match_counts: dict[str, int] = {}

    def record(self, result: FilterResult) -> None:
        """Record a filter result in the stats."""
        self.total_entries += 1

        if result.should_display:
            self.displayed_entries += 1
        else:
            self.ignored_entries += 1

            if result.matched_rule is not None:
                rule_key = self._rule_key(result.matched_rule)
                self.rule_match_counts[rule_key] = (
                    self.rule_match_counts.get(rule_key, 0) + 1
                )

    @staticmethod
    def _rule_key(rule: IgnoreRule) -> str:
        """Generate a string key for a rule."""
        return f"{type(rule).__name__}:{rule!r}"

    @property
    def filter_rate(self) -> float:
        """Calculate the percentage of entries that were filtered out."""
        if self.total_entries == 0:
            return 0.0
        return (self.ignored_entries / self.total_entries) * 100

    def summary(self) -> str:
        """Generate a summary string of filter stats."""
        lines = [
            f"Total entries: {self.total_entries}",
            f"Displayed: {self.displayed_entries}",
            f"Ignored: {self.ignored_entries} ({self.filter_rate:.1f}%)",
        ]

        if self.rule_match_counts:
            lines.append("\nRule match counts:")
            for rule_key, count in sorted(
                self.rule_match_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                lines.append(f"  {rule_key}: {count}")

        return "\n".join(lines)
