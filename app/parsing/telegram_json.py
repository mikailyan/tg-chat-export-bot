import json
from typing import Any, Optional

from .models import Participant, ParseResult
from .utils import extract_mentions, is_deleted_name, uniq_preserve

def _text_to_string(text_field: Any) -> str:
    if text_field is None:
        return ""
    if isinstance(text_field, str):
        return text_field
    if isinstance(text_field, list):
        parts = []
        for item in text_field:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "".join(parts)
    return str(text_field)

def _get_author(msg: dict) -> tuple[Optional[str], Optional[str], str]:
    """
    Возвращает (user_id, username, full_name)
    В экспортах поля могут отличаться, поэтому fallback’и.
    """
    full_name = (msg.get("from") or msg.get("actor") or "").strip()
    from_id = msg.get("from_id") or msg.get("actor_id")
    user_id = None
    if isinstance(from_id, str):
        user_id = "".join(ch for ch in from_id if ch.isdigit()) or from_id

    username = None
    if full_name.startswith("@"):
        username = full_name[1:]
        full_name = full_name

    return user_id, username, full_name

def parse_telegram_export_json(data: bytes) -> ParseResult:
    payload = json.loads(data.decode("utf-8", errors="replace"))

    messages = payload.get("messages")
    if not isinstance(messages, list):
        messages = payload.get("chat_history", {}).get("messages", [])

    participants_map: dict[str, Participant] = {}
    mentions_all: list[str] = []
    total_messages = 0

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("type") != "message":
            continue

        total_messages += 1

        user_id, username, full_name = _get_author(msg)
        if not full_name or is_deleted_name(full_name):
            pass
        else:
            key = None
            if user_id:
                key = f"id:{user_id}"
            elif username:
                key = f"u:{username.lower()}"
            else:
                key = f"n:{full_name.lower()}"

            if key not in participants_map:
                participants_map[key] = Participant(
                    user_id=user_id,
                    username=username,
                    full_name=full_name,
                    bio=None,
                )

        text_str = _text_to_string(msg.get("text"))
        mentions_all.extend(extract_mentions(text_str))

        ents = msg.get("text_entities")
        if isinstance(ents, list):
            for e in ents:
                if isinstance(e, dict) and e.get("type") == "mention":
                    t = e.get("text", "")
                    if isinstance(t, str) and t.startswith("@"):
                        mentions_all.append(t[1:])

    participants = list(participants_map.values())
    mentions = uniq_preserve(mentions_all)

    return ParseResult(participants=participants, mentions=mentions, total_messages=total_messages)
