# Scheduling System

Each channel can have one or more schedule rules that control when it prints. Rules use standard 5-field cron expressions and carry an explicit timezone, so prints fire at the correct local time regardless of where the device is running.

## Rule Format

A schedule rule is a JSON object with these fields:

| Field | Type | Description |
|---|---|---|
| `expression` | string | 5-field cron expression, e.g. `30 14 * * *` |
| `timezone` | string | IANA timezone name, e.g. `Australia/Sydney` |
| `enabled` | bool | Whether this rule is active |
| `description` | string | Auto-generated human-readable label |

Example rule set stored in channel config:

```json
"schedule_rules": [
  {
    "expression": "30 14 * * *",
    "timezone": "Australia/Sydney",
    "enabled": true,
    "description": "Every day at 14:30 (Australia/Sydney)"
  },
  {
    "expression": "0 9 * * 1-5",
    "timezone": "America/New_York",
    "enabled": true,
    "description": "Weekdays at 09:00 (America/New_York)"
  }
]
```

## Cron Expression Format

Rules use standard 5-field cron syntax:

```
┌─ minute    (0–59)
│ ┌─ hour     (0–23)
│ │ ┌─ day    (1–31)
│ │ │ ┌─ month (1–12)
│ │ │ │ ┌─ weekday (0–6, MON–SUN)
│ │ │ │ │
* * * * *
```

Common patterns:

| Expression | Meaning |
|---|---|
| `30 14 * * *` | Every day at 14:30 |
| `0 9 * * 1-5` | Weekdays at 09:00 |
| `*/30 * * * *` | Every 30 minutes |
| `0 8,12,18 * * *` | Three times daily at 08:00, 12:00, 18:00 |

### Inline Timezone Prefix

A rule's timezone can also be embedded directly in the expression using a `CRON_TZ=` prefix:

```
CRON_TZ=Europe/London 0 9 * * *
```

When present, this takes precedence over the rule's `timezone` field.

## Timezone Precedence

When evaluating a rule, the scheduler resolves its timezone in this order:

1. `CRON_TZ=` or `TZ=` prefix embedded in the expression (highest priority)
2. The `timezone` field on the rule itself
3. The channel-level `schedule_timezone` override
4. The global `settings.timezone`
5. UTC (final fallback)

## Scheduler Loop

The scheduler runs once per minute inside `app/main.py`. For each channel it iterates over all enabled `schedule_rules` and uses `croniter` to check whether the current minute matches the rule's expression evaluated in its resolved timezone. If matched, the channel print is triggered. Duplicate triggers within the same minute are suppressed.

## API

Schedule rules are managed via the channel schedule endpoint. The API accepts two payload shapes for backward compatibility:

**Legacy** (converted automatically on save):
```json
["09:30", "14:45"]
```

**Current**:
```json
{
  "timezone": "America/New_York",
  "rules": [
    { "expression": "30 9 * * *", "timezone": "America/New_York", "enabled": true }
  ]
}
```

Incoming rules are validated and normalized by `normalize_schedule_rules()` in `app/schedule_utils.py` before being written to config.

## Backend Utilities (`app/schedule_utils.py`)

| Function | Purpose |
|---|---|
| `resolve_timezone_name()` | Validates a timezone string; falls back safely to UTC |
| `parse_cron_with_timezone()` | Parses a cron expression, extracting any inline `CRON_TZ=` prefix |
| `hhmm_to_cron()` | Converts a legacy `HH:MM` string to a 5-field cron expression |
| `cron_to_human_text()` | Generates a human-readable label from a cron expression and timezone |
| `legacy_schedule_to_rules()` | Converts a legacy `schedule` list to `schedule_rules` format |
| `normalize_schedule_rules()` | Validates and normalizes an incoming API rule payload |

## Frontend

The Schedule Modal (`web/src/components/ScheduleModal.jsx`) lets users add and remove rules for a channel. It provides:

- A cron expression text input with format validation
- A timezone selector backed by `/api/system/timezone/list`
- A quick daily time picker that auto-populates the cron input
- A human-readable description rendered live from the entered expression, respecting the user's 12h/24h clock preference

Readable labels are always computed client-side from the raw expression at render time using `cronToReadable()` in `web/src/utils.js`, so they always reflect the current clock format setting rather than a stale saved string.

## Legacy Compatibility

Channels may still carry a `schedule` field (a list of `HH:MM` strings) from before the cron system was introduced. The frontend converts these to `schedule_rules` objects at display time. On next save, the channel is written in the new format only.

## Tests

- `testing/test_schedule.py` — unit tests for all `schedule_utils` functions
- `testing/test_scheduler_integration.py` — end-to-end rule evaluation across timezones, mixed formats, and edge cases
