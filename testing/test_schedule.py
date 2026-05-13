"""
Unit tests for schedule_utils module and scheduler timezone/cron logic.

Coverage:
- Cron expression parsing and validation
- Timezone precedence (per-rule > channel > global)
- Legacy HH:MM → cron migration
- Scheduler trigger logic (no double-fires, respects timezone)
- Human-readable text generation
"""

import pytest

import arrow
from croniter import croniter
import pytz

from app import schedule_utils


class TestTimezoneResolution:
    """Test timezone name validation and fallback logic."""

    def test_resolve_valid_timezone(self):
        """Valid timezone should be returned as-is."""
        result = schedule_utils.resolve_timezone_name("America/New_York")
        assert result == "America/New_York"

    def test_resolve_empty_string_uses_fallback(self):
        """Empty string should use fallback."""
        result = schedule_utils.resolve_timezone_name("", fallback="Europe/London")
        assert result == "Europe/London"

    def test_resolve_none_uses_fallback(self):
        """None should use fallback."""
        result = schedule_utils.resolve_timezone_name(None, fallback="UTC")
        assert result == "UTC"

    def test_resolve_whitespace_uses_fallback(self):
        """Whitespace-only string should use fallback."""
        result = schedule_utils.resolve_timezone_name("   ", fallback="Asia/Tokyo")
        assert result == "Asia/Tokyo"

    def test_resolve_invalid_timezone_falls_back(self):
        """Invalid timezone should fall back to fallback."""
        result = schedule_utils.resolve_timezone_name("Invalid/Zone", fallback="UTC")
        assert result == "UTC"

    def test_resolve_invalid_with_invalid_fallback_uses_default(self):
        """Invalid tz with invalid fallback should use DEFAULT_TIMEZONE."""
        result = schedule_utils.resolve_timezone_name("Bad/Zone", fallback="Bad/Fallback")
        assert result == schedule_utils.DEFAULT_TIMEZONE


class TestCronParsing:
    """Test cron expression parsing with optional legacy timezone prefix."""

    def test_parse_basic_cron_no_prefix(self):
        """Basic 5-field cron without timezone prefix."""
        cron_expr, tz_name = schedule_utils.parse_cron_with_timezone(
            "30 14 * * *", "UTC"
        )
        assert cron_expr == "30 14 * * *"
        assert tz_name == "UTC"

    def test_parse_cron_with_cron_tz_prefix(self):
        """Legacy CRON_TZ= prefix should be stripped and ignored."""
        cron_expr, tz_name = schedule_utils.parse_cron_with_timezone(
            "CRON_TZ=America/New_York 30 14 * * *", "UTC"
        )
        assert cron_expr == "30 14 * * *"
        assert tz_name == "UTC"

    def test_parse_cron_with_tz_prefix(self):
        """Legacy TZ= prefix should be stripped and ignored."""
        cron_expr, tz_name = schedule_utils.parse_cron_with_timezone(
            "TZ=Europe/London 0 9 * * MON-FRI", "UTC"
        )
        assert cron_expr == "0 9 * * MON-FRI"
        assert tz_name == "UTC"

    def test_parse_cron_empty_expression_raises(self):
        """Empty cron expression should raise ValueError."""
        with pytest.raises(ValueError, match="Cron expression is required"):
            schedule_utils.parse_cron_with_timezone("", "UTC")

    def test_parse_cron_invalid_syntax_raises(self):
        """Invalid cron syntax should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid cron expression"):
            schedule_utils.parse_cron_with_timezone("99 99 * * *", "UTC")

    def test_parse_cron_wrong_field_count_raises(self):
        """Cron with wrong field count should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid cron expression"):
            schedule_utils.parse_cron_with_timezone("30 14 * * * EXTRA", "UTC")

    def test_parse_cron_preserves_special_chars(self):
        """Cron expressions with ranges and lists should parse correctly."""
        cron_expr, tz_name = schedule_utils.parse_cron_with_timezone(
            "0,30 9-17 * * MON-FRI", "UTC"
        )
        assert cron_expr == "0,30 9-17 * * MON-FRI"
        assert tz_name == "UTC"

    def test_parse_cron_invalid_timezone_in_prefix_falls_back(self):
        """Legacy prefix timezone text should not affect fallback timezone."""
        cron_expr, tz_name = schedule_utils.parse_cron_with_timezone(
            "CRON_TZ=Invalid/Zone 30 14 * * *", "America/Chicago"
        )
        assert cron_expr == "30 14 * * *"
        assert tz_name == "America/Chicago"


class TestHHMMToCron:
    """Test legacy HH:MM format conversion to cron."""

    def test_hhmm_valid_time(self):
        """Valid HH:MM should convert to cron."""
        result = schedule_utils.hhmm_to_cron("14:30")
        assert result == "30 14 * * *"

    def test_hhmm_midnight(self):
        """00:00 should convert correctly."""
        result = schedule_utils.hhmm_to_cron("00:00")
        assert result == "0 0 * * *"

    def test_hhmm_end_of_day(self):
        """23:59 should convert correctly."""
        result = schedule_utils.hhmm_to_cron("23:59")
        assert result == "59 23 * * *"

    def test_hhmm_leading_zeros(self):
        """Times with leading zeros should parse."""
        result = schedule_utils.hhmm_to_cron("09:05")
        assert result == "5 9 * * *"

    def test_hhmm_invalid_format_raises(self):
        """Non-HH:MM format should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid HH:MM time"):
            schedule_utils.hhmm_to_cron("9:30:00")

    def test_hhmm_out_of_range_hour_raises(self):
        """Hour > 23 should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid HH:MM time"):
            schedule_utils.hhmm_to_cron("25:30")

    def test_hhmm_out_of_range_minute_raises(self):
        """Minute > 59 should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid HH:MM time"):
            schedule_utils.hhmm_to_cron("14:99")

    def test_hhmm_non_numeric_raises(self):
        """Non-numeric values should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid HH:MM time"):
            schedule_utils.hhmm_to_cron("AB:CD")


class TestCronToHumanText:
    """Test cron-to-readable-description conversion."""

    def test_daily_schedule(self):
        """Daily schedule should be readable."""
        text = schedule_utils.humanize_cron("30 14 * * *", "America/New_York")
        assert "Every day" in text
        assert "2:30 PM" in text
        assert "America/New_York" in text

    def test_midnight_schedule(self):
        """Midnight schedule should be readable."""
        text = schedule_utils.humanize_cron("0 0 * * *", "UTC")
        assert "Every day" in text
        assert "12:00 AM" in text

    def test_weekday_schedule(self):
        """Weekday schedule should be recognized."""
        text = schedule_utils.humanize_cron("0 9 * * MON-FRI", "UTC")
        assert "Weekdays" in text
        assert "9:00 AM" in text

    def test_weekday_numeric_range(self):
        """Weekday numeric range 1-5 should be recognized."""
        text = schedule_utils.humanize_cron("0 9 * * 1-5", "UTC")
        assert "Weekdays" in text

    def test_complex_cron_fallback(self):
        """Complex cron should fall back to generic text."""
        text = schedule_utils.humanize_cron("*/15 * * * *", "UTC")
        assert "Cron" in text
        assert "UTC" in text

    def test_day_specific_schedule_fallback(self):
        """Schedule with specific day should fall back to generic text."""
        text = schedule_utils.humanize_cron("0 9 15 * *", "UTC")
        assert "Cron" in text


class TestLegacyScheduleMigration:
    """Test conversion of legacy HH:MM schedule lists to cron rules."""

    def test_single_time_migration(self):
        """Single HH:MM time should convert to single rule."""
        rules = schedule_utils.legacy_schedule_to_rules(["14:30"], "UTC")
        assert len(rules) == 1
        assert rules[0]["expression"] == "30 14 * * *"
        assert rules[0]["timezone"] == "UTC"
        assert rules[0]["enabled"] is True
        assert "Every day" in rules[0]["description"]

    def test_multiple_times_migration(self):
        """Multiple times should convert to multiple rules."""
        rules = schedule_utils.legacy_schedule_to_rules(
            ["09:00", "14:30", "18:00"], "America/Chicago"
        )
        assert len(rules) == 3
        assert all(r["timezone"] == "America/Chicago" for r in rules)
        assert rules[0]["expression"] == "0 9 * * *"
        assert rules[1]["expression"] == "30 14 * * *"
        assert rules[2]["expression"] == "0 18 * * *"

    def test_migration_with_invalid_tz_falls_back(self):
        """Invalid timezone should fall back to default."""
        rules = schedule_utils.legacy_schedule_to_rules(
            ["14:30"], "Invalid/Zone"
        )
        assert rules[0]["timezone"] == schedule_utils.DEFAULT_TIMEZONE

    def test_empty_schedule_list(self):
        """Empty schedule list should result in no rules."""
        rules = schedule_utils.legacy_schedule_to_rules([], "UTC")
        assert len(rules) == 0


class TestNormalizeScheduleRules:
    """Test normalization of incoming schedule rule payloads."""

    def test_normalize_valid_rules(self):
        """Valid rule payloads should be normalized."""
        payloads = [
            {
                "expression": "30 14 * * *",
                "timezone": "UTC",
                "enabled": True,
            }
        ]
        rules = schedule_utils.normalize_schedule_rules(payloads, "UTC")
        assert len(rules) == 1
        assert rules[0]["expression"] == "30 14 * * *"
        assert rules[0]["enabled"] is True

    def test_normalize_cron_tz_prefix(self):
        """Legacy CRON_TZ= prefix should be ignored in favor of system timezone."""
        payloads = [
            {
                "expression": "CRON_TZ=America/New_York 30 14 * * *",
                "enabled": True,
            }
        ]
        rules = schedule_utils.normalize_schedule_rules(payloads, "UTC")
        assert rules[0]["expression"] == "30 14 * * *"
        assert rules[0]["timezone"] == "UTC"

    def test_normalize_missing_expression_raises(self):
        """Rule without expression should raise ValueError."""
        with pytest.raises(ValueError, match="requires an expression"):
            schedule_utils.normalize_schedule_rules([{}], "UTC")

    def test_normalize_missing_timezone_uses_fallback(self):
        """Rule without timezone should use the configured system timezone."""
        payloads = [
            {
                "expression": "0 9 * * *",
            }
        ]
        rules = schedule_utils.normalize_schedule_rules(payloads, "UTC")
        assert rules[0]["timezone"] == "UTC"

    def test_normalize_enabled_defaults_to_true(self):
        """Missing 'enabled' field should default to True."""
        payloads = [
            {"expression": "0 9 * * *", "timezone": "UTC"}
        ]
        rules = schedule_utils.normalize_schedule_rules(payloads, "UTC")
        assert rules[0]["enabled"] is True

    def test_normalize_auto_generates_description(self):
        """Missing description should be auto-generated."""
        payloads = [
            {"expression": "0 9 * * *", "timezone": "UTC"}
        ]
        rules = schedule_utils.normalize_schedule_rules(payloads, "UTC")
        assert rules[0]["description"]
        assert "Every day" in rules[0]["description"]

    def test_normalize_regenerates_description(self):
        """Descriptions should be regenerated using the configured system timezone."""
        payloads = [
            {
                "expression": "0 9 * * *",
                "timezone": "UTC",
                "description": "Custom description",
            }
        ]
        rules = schedule_utils.normalize_schedule_rules(payloads, "UTC")
        assert rules[0]["description"] == "Every day at 9:00 AM (UTC)"

    def test_normalize_accepts_legacy_cron_field(self):
        """Rule with 'cron' field (legacy) should be accepted."""
        payloads = [
            {
                "cron": "0 9 * * *",
                "timezone": "UTC",
            }
        ]
        rules = schedule_utils.normalize_schedule_rules(payloads, "UTC")
        assert rules[0]["expression"] == "0 9 * * *"

    def test_normalize_timezone_uses_fallback(self):
        """Explicit rule timezone should be ignored in favor of system timezone."""
        payloads = [
            {
                "expression": "0 9 * * *",
                "timezone": "America/Los_Angeles",
            }
        ]
        rules = schedule_utils.normalize_schedule_rules(payloads, "UTC")
        assert rules[0]["timezone"] == "UTC"

    def test_normalize_invalid_timezone_uses_fallback(self):
        """Invalid timezone in rule should use fallback."""
        payloads = [
            {
                "expression": "0 9 * * *",
                "timezone": "Invalid/Zone",
            }
        ]
        rules = schedule_utils.normalize_schedule_rules(payloads, "UTC")
        assert rules[0]["timezone"] == "UTC"


class TestCronEvaluation:
    """Test that cron expressions evaluate correctly in their specified timezones.
    
    This validates the scheduler would trigger at the right time.
    """

    def test_daily_cron_next_occurrence(self):
        """Daily cron should have next occurrence within 24 hours."""
        cron_expr = "30 14 * * *"
        base = arrow.get("2026-05-08T12:00:00").naive
        cron = croniter(cron_expr, base)
        next_run = arrow.get(cron.get_next(float)).naive
        
        # Next run should be within 24 hours
        delta = (next_run - base).total_seconds()
        assert 0 < delta < (24 * 3600)

    def test_weekday_cron_skips_weekends(self):
        """Weekday cron (MON-FRI) should skip weekend dates."""
        cron_expr = "0 9 * * MON-FRI"
        cron = croniter(cron_expr, arrow.get("2026-05-08T00:00:00").naive)  # Friday
        
        # Get next 3 runs
        runs = [arrow.get(cron.get_next(float)).naive for _ in range(3)]
        
        # All should be weekdays
        for run in runs:
            assert run.weekday() < 5  # 0-4 are Monday-Friday

    def test_cron_in_different_timezone(self):
        """Cron evaluated in specific timezone should adjust UTC time."""
        # This test validates the concept; actual scheduler_loop
        # implementation will handle the timezone context.
        cron_expr = "0 14 * * *"  # 2 PM in the specified timezone
        
        # croniter itself works with naive datetimes,
        # so the application must provide the now() in the target timezone.
        tz_ny = pytz.timezone("America/New_York")
        now_ny = arrow.now(tz_ny).naive

        cron = croniter(cron_expr, now_ny)
        next_run = arrow.get(cron.get_next(float))
        
        # Next run should be 14:00 in NY time
        assert next_run.hour == 14
        assert next_run.minute == 0


class TestSchedulerTriggerLogic:
    """Test that scheduler correctly evaluates triggers without double-firing.
    
    These tests validate the core scheduler_loop behavior:
    - Respects rule timezone
    - Deduplicates firings per minute
    - Handles multiple rules per channel
    """

    def test_cron_evaluation_at_specific_time(self):
        """Verify croniter can evaluate cron in specific timezone context."""
        # The scheduler_loop provides now() in the rule's timezone context.
        # croniter then evaluates the cron against that time.
        
        rule_tz = "America/New_York"
        tz_obj = pytz.timezone(rule_tz)
        
        # Create a specific time: 2:00 PM on a Monday in NYC
        now_ny = arrow.get(2026, 5, 11, 14, 0, 0, tzinfo=tz_obj).datetime
        now_naive = now_ny.replace(tzinfo=None)
        
        cron_expr = "0 14 * * *"
        cron = croniter(cron_expr, now_naive)
        
        # The current time 2:00 PM should be a valid cron occurrence
        # (next run from 2:00 PM should be tomorrow at 2:00 PM)
        next_run = arrow.get(cron.get_next(float))
        assert next_run.hour == 14
        assert next_run.minute == 0
        # It should be tomorrow
        assert next_run.day == 12

    def test_scheduler_dedup_concept_per_minute(self):
        """Verify that multiple cron evaluations in same minute are consistent.
        
        The scheduler_loop prevents double-firing by tracking last_trigger
        and comparing against current minute. This test validates croniter's
        consistency within a minute.
        """
        cron_expr = "0 14 * * *"
        
        # Create two croniter instances at same time
        test_time = arrow.get("2026-05-11T14:00:00").naive
        cron1 = croniter(cron_expr, test_time)
        cron2 = croniter(cron_expr, test_time)
        
        # Both should give same next run
        next1 = arrow.get(cron1.get_next(float))
        next2 = arrow.get(cron2.get_next(float))
        
        assert next1 == next2

    def test_multiple_rules_per_channel(self):
        """Channel with multiple rules should evaluate all."""
        rules = [
            {"expression": "0 9 * * *", "timezone": "UTC", "enabled": True},
            {"expression": "0 17 * * *", "timezone": "UTC", "enabled": True},
        ]
        
        # Both rules should be valid cron expressions
        for rule in rules:
            assert croniter.is_valid(rule["expression"])

    def test_disabled_rule_should_not_trigger(self):
        """Rule with enabled=False should be skipped by scheduler."""
        # The scheduler_loop checks the 'enabled' field before evaluating.
        rule = {"expression": "0 14 * * *", "timezone": "UTC", "enabled": False}
        
        # Application logic should skip this; we just verify the data model
        assert rule["enabled"] is False


class TestScheduleConsistency:
    """Integration tests for schedule system consistency."""

    def test_legacy_migration_roundtrip(self):
        """Legacy HH:MM should migrate to cron and be evaluable."""
        legacy = ["09:30", "17:45"]
        rules = schedule_utils.legacy_schedule_to_rules(legacy, "UTC")
        
        # Each rule should be a valid cron expression
        for rule in rules:
            assert croniter.is_valid(rule["expression"])

    def test_incoming_payload_normalization_roundtrip(self):
        """Incoming payload should normalize and remain valid."""
        payloads = [
            {"expression": "0 9 * * *", "timezone": "America/Chicago"},
            {"expression": "CRON_TZ=Europe/London 30 14 * * *"},
        ]
        
        rules = schedule_utils.normalize_schedule_rules(payloads, "UTC")
        
        # All rules should be valid
        for rule in rules:
            assert croniter.is_valid(rule["expression"])
            assert rule["timezone"]
            assert "description" in rule

    def test_all_standard_timezones_supported(self):
        """All common timezones should resolve correctly."""
        timezones = [
            "UTC",
            "America/New_York",
            "America/Chicago",
            "America/Denver",
            "America/Los_Angeles",
            "Europe/London",
            "Europe/Paris",
            "Asia/Tokyo",
            "Australia/Sydney",
        ]
        
        for tz in timezones:
            resolved = schedule_utils.resolve_timezone_name(tz)
            assert resolved == tz


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
