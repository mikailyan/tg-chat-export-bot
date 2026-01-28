from bs4 import BeautifulSoup

from .models import Participant, ParseResult
from .utils import extract_mentions, is_deleted_name, uniq_preserve

def parse_telegram_export_html(data: bytes) -> ParseResult:
    html = data.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "lxml")

    participants_map: dict[str, Participant] = {}
    mentions_all: list[str] = []
    total_messages = 0

    for msg_div in soup.select("div.message"):
        total_messages += 1

        from_name = ""
        fn = msg_div.select_one(".from_name")
        if fn:
            from_name = fn.get_text(strip=True)

        text = ""
        body = msg_div.select_one(".text")
        if body:
            text = body.get_text(" ", strip=True)

        mentions_all.extend(extract_mentions(text))

        if from_name and not is_deleted_name(from_name):
            key = f"n:{from_name.lower()}"
            if key not in participants_map:
                participants_map[key] = Participant(
                    user_id=None,
                    username=None,
                    full_name=from_name,
                    bio=None,
                )

    participants = list(participants_map.values())
    mentions = uniq_preserve(mentions_all)

    return ParseResult(participants=participants, mentions=mentions, total_messages=total_messages)
