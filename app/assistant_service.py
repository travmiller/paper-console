"""
Assistant service for the Settings UI.

This is intentionally stateless (no server-side chat history) and uses the
Telegram AI credentials (provider/key/model) configured in Settings.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


ASSISTANT_SYSTEM_PROMPT_BASE = """You are a helpful AI assistant for the PC-1 Paper Console.

ALWAYS respond with JSON only. You have NO MEMORY between messages.

You can propose these response types:

1) Normal message:
{"type":"message","message":"..."}

2) Propose printing AI-generated content (requires user confirmation in UI):
{"type":"print","title":"Title","content":"Text to print"}

3) Propose running a channel (requires confirmation):
{"type":"run_channel","channel":1}

4) Propose running a module by type (requires confirmation):
{"type":"run_module","module_type":"maze"}

5) Propose configuration changes (requires confirmation):
{
  "type":"config_plan",
  "summary":"One sentence of what will change",
  "operations":[
    {"op":"swap_channels","a":1,"b":2},
    {"op":"create_module","temp_id":"m1","module_type":"rss","name":"Morning Feeds","config":{},"assign_to_channel":3,"order":0},
    {"op":"assign_module_to_channel","channel":3,"module_ref":"m1","order":1},
    {"op":"reorder_channel_modules","channel":3,"module_orders":{"<module_id>":0}},
    {"op":"update_channel_schedule","channel":3,"schedule":["07:30","18:00"]},
    {"op":"rename_module","module_id":"<uuid>","name":"New Name"},
    {"op":"remove_module_from_channel","channel":3,"module_id":"<uuid>"}
  ]
}

RULES:
- Keep operations minimal and safe.
- Prefer existing module types; you cannot create new Python module types on the fly.
- If a user asks for a new type, approximate using existing types (webhook/text/rss/calendar/etc.).
- Channels are 1-8.
- Schedules must be HH:MM in 24h time.
"""


def _build_context() -> str:
    """Build dynamic context about current settings and available module types."""
    try:
        from app.config import settings
        from app.module_registry import get_all_modules
        from datetime import datetime
        import pytz

        try:
            tz = pytz.timezone(settings.timezone)
            now = datetime.now(tz)
            time_str = now.strftime("%A, %B %d, %Y %I:%M %p")
        except Exception:
            time_str = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")

        lines = [
            "\n--- DEVICE CONTEXT ---",
            f"Location: {settings.city_name}" + (f", {settings.state}" if settings.state else ""),
            f"Timezone: {settings.timezone}",
            f"Current time: {time_str}",
            "",
            "Channels (1-8):",
        ]

        for ch_num in range(1, 9):
            ch_config = settings.channels.get(ch_num)
            if ch_config and ch_config.modules:
                sorted_assignments = sorted(ch_config.modules, key=lambda a: a.order)
                parts = []
                for assignment in sorted_assignments[:4]:
                    mod = settings.modules.get(assignment.module_id)
                    if mod:
                        parts.append(f"{mod.name} ({mod.type}) [{mod.id}]")
                if not parts:
                    parts.append("[empty]")
                if len(sorted_assignments) > 4:
                    parts.append("…")
                lines.append(f"  {ch_num}: " + " | ".join(parts))
            else:
                lines.append(f"  {ch_num}: [empty]")

        defs = get_all_modules()
        type_ids = sorted(defs.keys())
        lines.append("")
        lines.append("Available module types:")
        lines.append(", ".join(type_ids))

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Failed to build assistant context: {e}")
        return ""


@dataclass
class AssistantResult:
    payload: Dict[str, Any]
    raw_text: str


class AssistantService:
    def __init__(self, config):
        self.config = config
        self._ai_client: Optional[Any] = None

    def init_client(self) -> None:
        if not self.config or not getattr(self.config, "ai_api_key", None):
            self._ai_client = None
            return

        provider = (getattr(self.config, "ai_provider", "") or "").lower()
        if provider == "anthropic":
            if not HAS_ANTHROPIC:
                raise RuntimeError("Anthropic library not installed")
            self._ai_client = anthropic.Anthropic(api_key=self.config.ai_api_key)
        elif provider == "openai":
            if not HAS_OPENAI:
                raise RuntimeError("OpenAI library not installed")
            self._ai_client = openai.OpenAI(api_key=self.config.ai_api_key)
        else:
            raise RuntimeError(f"Unknown AI provider: {provider}")

    def _get_model(self) -> str:
        if getattr(self.config, "ai_model", None):
            return self.config.ai_model

        provider = (getattr(self.config, "ai_provider", "") or "").lower()
        if provider == "anthropic":
            return "claude-sonnet-4-20250514"
        if provider == "openai":
            return "gpt-4o-mini"
        return "gpt-4o-mini"

    def chat_once(self, message: str) -> AssistantResult:
        if not self._ai_client:
            raise RuntimeError("AI is not configured")

        provider = (getattr(self.config, "ai_provider", "") or "").lower()
        model = self._get_model()

        system_prompt = ASSISTANT_SYSTEM_PROMPT_BASE + _build_context()

        if provider == "anthropic":
            response = self._ai_client.messages.create(
                model=model,
                max_tokens=1400,
                system=system_prompt,
                messages=[{"role": "user", "content": message}],
            )
            raw = response.content[0].text
        else:
            response = self._ai_client.chat.completions.create(
                model=model,
                max_tokens=1400,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
            )
            raw = response.choices[0].message.content

        parsed = self.parse_response(raw)
        return AssistantResult(payload=parsed, raw_text=raw)

    def parse_response(self, text: str) -> Dict[str, Any]:
        text = (text or "").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {"type": "message", "message": text}

        # Back-compat with Telegram bot JSON format
        if "type" not in data:
            if "action" in data:
                if data["action"] == "run_channel":
                    return {"type": "run_channel", "channel": int(data.get("channel", 1))}
                if data["action"] == "run_module":
                    return {"type": "run_module", "module_type": data.get("type", "")}
            if data.get("print"):
                return {
                    "type": "print",
                    "title": (data.get("title") or "ASSISTANT")[:30],
                    "content": data.get("content", ""),
                }
            if "message" in data:
                return {"type": "message", "message": data.get("message", "")}
            return {"type": "message", "message": text}

        rtype = data.get("type")
        if rtype == "message":
            return {"type": "message", "message": data.get("message", "")}
        if rtype == "print":
            return {
                "type": "print",
                "title": (data.get("title") or "ASSISTANT")[:30],
                "content": data.get("content", ""),
            }
        if rtype == "run_channel":
            return {"type": "run_channel", "channel": int(data.get("channel", 1))}
        if rtype == "run_module":
            return {"type": "run_module", "module_type": data.get("module_type", "")}
        if rtype == "config_plan":
            ops = data.get("operations") if isinstance(data.get("operations"), list) else []
            return {
                "type": "config_plan",
                "summary": data.get("summary", ""),
                "operations": ops,
            }

        return {"type": "message", "message": text}

