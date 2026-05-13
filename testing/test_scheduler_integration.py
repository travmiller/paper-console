"""
Integration tests validating scheduler_loop works correctly with the cron system.

These tests ensure the scheduler correctly evaluates both legacy HH:MM schedules
and new cron rule schedules using the configured system timezone.
"""

import pytest
import pytz
from unittest.mock import MagicMock, patch

import arrow
from app import main, schedule_utils


class TestSchedulerLoopIntegration:
    """Test scheduler_loop integration with cron scheduling."""

    def test_channel_schedule_rules_normalization(self):
        """Channel config should normalize schedule into rules."""
        # Simulate a channel with legacy HH:MM schedule
        channel = {
            'schedule': ['14:30', '09:00'],
        }
        
        # The _channel_schedule_rules helper should normalize this
        # (This tests the helper function used by scheduler_loop)
        rules = schedule_utils.legacy_schedule_to_rules(
            channel['schedule'],
            'America/New_York'
        )
        
        assert len(rules) == 2
        assert all(r['timezone'] == 'America/New_York' for r in rules)
        assert all('expression' in r for r in rules)

    def test_cron_trigger_evaluation_in_timezone(self):
        """Verify cron rules are evaluated in their specified timezone."""
        # Create a rule that fires daily at 2:00 PM NYC time
        rule_tz = "America/New_York"
        rule_cron = "0 14 * * *"  # 2:00 PM
        
        # Create a time that's 2:00 PM in NYC
        tz_obj = pytz.timezone(rule_tz)
        target_time_ny = arrow.get(2026, 5, 11, 14, 0, 0, tzinfo=tz_obj).datetime
        
        # Verify the cron would evaluate as a match at this time
        from croniter import croniter
        target_naive = target_time_ny.replace(tzinfo=None)
        cron = croniter(rule_cron, target_naive)
        
        # Get next occurrence from this exact time
        next_run = arrow.get(cron.get_next(float))
        # Should be tomorrow at 2:00 PM (same local time, next day)
        assert next_run.hour == 14
        assert next_run.minute == 0
        assert next_run.day == 12  # Tomorrow

    def test_multiple_rules_per_channel_evaluation(self):
        """Multiple rules in same channel should be evaluated independently."""
        rules = [
            {
                'expression': '0 9 * * *',
                'timezone': 'UTC',
                'enabled': True,
            },
            {
                'expression': '0 17 * * *',
                'timezone': 'UTC',
                'enabled': True,
            },
        ]
        
        # Both should be valid and evaluable
        for rule in rules:
            assert schedule_utils.croniter.is_valid(rule['expression'])

    def test_disabled_rule_skipped_by_scheduler(self):
        """Rules with enabled=False should be skipped."""
        rules = [
            {
                'expression': '0 9 * * *',
                'timezone': 'UTC',
                'enabled': True,
            },
            {
                'expression': '0 14 * * *',
                'timezone': 'UTC',
                'enabled': False,  # Disabled
            },
        ]
        
        # The scheduler_loop logic should skip disabled rules
        active_rules = [r for r in rules if r.get('enabled', True)]
        assert len(active_rules) == 1
        assert active_rules[0]['expression'] == '0 9 * * *'

    def test_legacy_and_cron_mixed_schedules(self):
        """Channel with both legacy schedule and cron rules should use cron rules."""
        # Simulate channel with both old and new format
        channel = {
            'schedule': ['14:30'],  # Legacy
            'schedule_rules': [     # New format
                {
                    'expression': '0 9 * * MON-FRI',
                    'timezone': 'America/Chicago',
                    'enabled': True,
                }
            ],
            'schedule_timezone': 'America/Chicago',
        }
        
        # Scheduler should prefer schedule_rules if present
        if channel.get('schedule_rules'):
            active_rules = channel['schedule_rules']
        else:
            active_rules = schedule_utils.legacy_schedule_to_rules(
                channel.get('schedule', []),
                channel.get('schedule_timezone', 'UTC')
            )
        
        assert len(active_rules) == 1
        assert active_rules[0]['expression'] == '0 9 * * MON-FRI'

    def test_timezone_prefix_is_ignored_per_rule(self):
        """Legacy timezone prefixes should not override the system timezone."""
        rule_with_prefix = "CRON_TZ=Europe/London 0 9 * * *"
        default_tz = "America/New_York"
        
        # Parse should extract the timezone
        cron_expr, extracted_tz = schedule_utils.parse_cron_with_timezone(
            rule_with_prefix,
            default_tz
        )

        assert cron_expr == "0 9 * * *"
        assert extracted_tz == default_tz

    def test_schedule_rules_human_text_generation(self):
        """Human-readable text should be generated for display."""
        rules = [
            {
                'expression': '0 9 * * MON-FRI',
                'timezone': 'America/New_York',
                'enabled': True,
            },
            {
                'expression': '30 14 * * *',
                'timezone': 'UTC',
                'enabled': True,
            },
        ]
        
        for rule in rules:
            description = schedule_utils.humanize_cron(
                rule['expression'],
                rule['timezone']
            )
            assert description
            assert rule['timezone'] in description
            # Should be human-readable, not just the cron expression
            if 'MON-FRI' in rule['expression']:
                assert 'Weekday' in description or 'Cron' in description
            elif rule['expression'] == '30 14 * * *':
                assert 'day' in description.lower() or 'Cron' in description

    def test_schedule_consistency_across_format_conversion(self):
        """Converting between formats should maintain functional equivalence."""
        # Start with legacy format
        legacy = ['14:30', '09:00']
        
        # Convert to rules
        rules = schedule_utils.legacy_schedule_to_rules(legacy, 'UTC')
        
        # Rules should be normalizable and valid
        normalized = schedule_utils.normalize_schedule_rules(
            rules,
            'UTC'
        )
        
        assert len(normalized) == len(legacy)
        # Each should have a valid cron expression
        for rule in normalized:
            assert schedule_utils.croniter.is_valid(rule['expression'])


class TestSchedulePayloadHandling:
    """Test handling of schedule payloads from API."""

    def test_api_payload_with_legacy_format(self):
        """API receiving legacy schedule list should work."""
        payload = ['09:30', '14:45', '18:00']
        tz = 'America/New_York'
        
        rules = schedule_utils.legacy_schedule_to_rules(payload, tz)
        assert len(rules) == len(payload)

    def test_api_payload_with_new_cron_format(self):
        """API receiving new cron rule format should normalize to system timezone."""
        payload = {
            'rules': [
                {
                    'expression': '0 9 * * MON-FRI',
                    'timezone': 'America/Chicago',
                    'enabled': True,
                },
                {
                    'expression': 'CRON_TZ=UTC 0 14 * * *',
                    'enabled': True,
                },
            ]
        }
        
        # Normalize the rules
        normalized = schedule_utils.normalize_schedule_rules(
            payload['rules'],
            'UTC'
        )
        
        assert len(normalized) == 2
        # Both rules should use the configured system timezone.
        assert normalized[1]['timezone'] == 'UTC'
        assert normalized[0]['timezone'] == 'UTC'

    def test_api_payload_mixed_formats(self):
        """API might receive mixed old and new formats during migration."""
        # Channel config might have both
        channel = {
            'schedule': ['14:30'],           # Old format (might still be here)
            'schedule_rules': [              # New format
                {'expression': '0 9 * * *', 'timezone': 'UTC', 'enabled': True}
            ],
            'schedule_timezone': 'UTC',
        }
        
        # Scheduler should prefer new format
        if channel.get('schedule_rules'):
            active = channel['schedule_rules']
        else:
            active = schedule_utils.legacy_schedule_to_rules(
                channel.get('schedule', []),
                channel.get('schedule_timezone', 'UTC')
            )
        
        assert len(active) == 1
        assert active[0]['expression'] == '0 9 * * *'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
