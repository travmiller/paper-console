from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

import arrow
from croniter import croniter
import pytz


DEFAULT_TIMEZONE = "UTC"


def resolve_timezone_name(timezone_name: Optional[str], fallback: str = DEFAULT_TIMEZONE) -> str:
    candidate = (timezone_name or "").strip()
    if not candidate:
        candidate = fallback

    try:
        pytz.timezone(candidate)
        return candidate
    except Exception:
        try:
            pytz.timezone(fallback)
            return fallback
        except Exception:
            return DEFAULT_TIMEZONE


def parse_cron_with_timezone(raw_expression: str, fallback_timezone: str) -> Tuple[str, str]:
    expression = str(raw_expression or "").strip()
    timezone_name = resolve_timezone_name(fallback_timezone)

    if not expression:
        raise ValueError("Cron expression is required")

    parts = expression.split()
    if not parts:
        raise ValueError("Cron expression is required")

    first = parts[0]
    if first.startswith("CRON_TZ=") or first.startswith("TZ="):
        _, _, tz_value = first.partition("=")
        timezone_name = resolve_timezone_name(tz_value, fallback=timezone_name)
        parts = parts[1:]

    cron_expression = " ".join(parts).strip()
    if not cron_expression:
        raise ValueError("Cron expression is required")

    if not croniter.is_valid(cron_expression):
        raise ValueError(f"Invalid cron expression: '{raw_expression}'")

    field_count = len(cron_expression.split())
    if field_count != 5:
        raise ValueError("Cron expression must contain exactly 5 fields")

    return cron_expression, timezone_name


def hhmm_to_cron(time_value: str) -> str:
    normalized = str(time_value or "").strip()
    parts = normalized.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid HH:MM time '{time_value}'")

    hour_text, minute_text = parts
    if not hour_text.isdigit() or not minute_text.isdigit():
        raise ValueError(f"Invalid HH:MM time '{time_value}'")

    hour = int(hour_text)
    minute = int(minute_text)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid HH:MM time '{time_value}'")

    return f"{minute} {hour} * * *"


def humanize_cron(cron_expression: str, timezone_name: str) -> str:
    minute, hour, day, month, weekday = cron_expression.split()

    if day == "*" and month == "*" and weekday == "*" and minute.isdigit() and hour.isdigit():
        time_label = arrow.get(2000, 1, 1, int(hour), int(minute)).format("h:mm A")
        return f"Every day at {time_label} ({timezone_name})"

    if day == "*" and month == "*" and weekday in {"1-5", "MON-FRI", "mon-fri"} and minute.isdigit() and hour.isdigit():
        time_label = arrow.get(2000, 1, 3, int(hour), int(minute)).format("h:mm A")
        return f"Weekdays at {time_label} ({timezone_name})"

    return f"Cron '{cron_expression}' ({timezone_name})"


def legacy_schedule_to_rules(
    schedule_times: Sequence[str],
    timezone_name: str,
) -> list[dict]:
    resolved_timezone = resolve_timezone_name(timezone_name)
    rules: list[dict] = []

    for time_value in schedule_times:
        cron_expression = hhmm_to_cron(time_value)
        rules.append(
            {
                "expression": cron_expression,
                "timezone": resolved_timezone,
                "enabled": True,
                "description": humanize_cron(cron_expression, resolved_timezone),
            }
        )

    return rules


def normalize_schedule_rules(
    rule_payloads: Iterable[dict],
    fallback_timezone: str,
) -> list[dict]:
    resolved_fallback = resolve_timezone_name(fallback_timezone)
    rules: list[dict] = []

    for raw_rule in rule_payloads:
        expression_text = str(raw_rule.get("expression") or raw_rule.get("cron") or "").strip()
        if not expression_text:
            raise ValueError("Each schedule rule requires an expression")

        parts = expression_text.split()
        first = parts[0] if parts else ""
        has_inline_timezone = first.startswith("CRON_TZ=") or first.startswith("TZ=")

        explicit_timezone = str(raw_rule.get("timezone") or "").strip()
        if not explicit_timezone and not has_inline_timezone:
            raise ValueError("Each schedule rule requires a timezone")

        tz_hint = explicit_timezone or resolved_fallback
        cron_expression, timezone_name = parse_cron_with_timezone(expression_text, tz_hint)

        enabled = bool(raw_rule.get("enabled", True))
        description = str(raw_rule.get("description") or "").strip()
        if not description:
            description = humanize_cron(cron_expression, timezone_name)

        rules.append(
            {
                "expression": cron_expression,
                "timezone": timezone_name,
                "enabled": enabled,
                "description": description,
            }
        )

    return rules
